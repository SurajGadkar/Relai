"""
Test suite for Smart Background Cleanup feature.
Tests the remove_background() function and the /upload endpoint integration.
"""
import io
import sys
import time
import sqlite3
from PIL import Image

# --- Test 1: Unit test remove_background with a real image ---
def test_remove_background_with_real_image():
    """Generate a synthetic clothing-like image and verify background removal works."""
    print("\n=== TEST 1: remove_background with a real image ===")
    
    from rembg import remove
    from main import remove_background

    # Create a test image: colored rectangle (simulating a shirt) on a noisy background
    img = Image.new("RGB", (400, 400), color=(200, 200, 200))  # grey background
    # Draw a "shirt" shape in the center
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 80, 300, 350], fill=(30, 60, 120))  # dark blue shirt
    draw.rectangle([80, 80, 120, 200], fill=(30, 60, 120))    # left sleeve
    draw.rectangle([280, 80, 320, 200], fill=(30, 60, 120))   # right sleeve

    # Convert to bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    original_bytes = buf.getvalue()

    print(f"  Input size: {len(original_bytes)} bytes")
    
    start = time.time()
    result_bytes = remove_background(original_bytes)
    elapsed = time.time() - start
    
    print(f"  Output size: {len(result_bytes)} bytes")
    print(f"  Processing time: {elapsed:.2f}s")

    # Verify output is a valid image
    result_img = Image.open(io.BytesIO(result_bytes))
    print(f"  Output mode: {result_img.mode} (expecting RGBA)")
    print(f"  Output dimensions: {result_img.size}")

    # Verify RGBA (transparency channel exists)
    assert result_img.mode == "RGBA", f"Expected RGBA, got {result_img.mode}"
    
    # Verify some pixels are transparent (background removed)
    alpha = result_img.getchannel("A")
    pixels = list(alpha.getdata())
    transparent_count = sum(1 for p in pixels if p < 128)
    total = len(pixels)
    transparency_pct = (transparent_count / total) * 100
    
    print(f"  Transparent pixels: {transparent_count}/{total} ({transparency_pct:.1f}%)")
    assert transparent_count > 0, "Expected some transparent pixels after background removal"
    
    print("  ✅ PASSED: Background removal produces valid RGBA image with transparency")
    return True


# --- Test 2: Fallback on corrupt data ---
def test_remove_background_with_corrupt_data():
    """Verify graceful fallback when given corrupt/non-image data."""
    print("\n=== TEST 2: remove_background with corrupt data (fallback test) ===")
    
    from main import remove_background

    corrupt_data = b"this is not an image at all, just random bytes!!!!"
    
    result = remove_background(corrupt_data)
    
    # Should return the original data as fallback
    assert result == corrupt_data, "Expected fallback to return original bytes"
    print("  ✅ PASSED: Gracefully fell back to original data on corrupt input")
    return True


# --- Test 3: Empty bytes ---
def test_remove_background_with_empty_bytes():
    """Verify graceful fallback when given empty bytes."""
    print("\n=== TEST 3: remove_background with empty bytes ===")
    
    from main import remove_background

    result = remove_background(b"")
    
    assert result == b"", "Expected fallback to return empty bytes"
    print("  ✅ PASSED: Gracefully handled empty bytes")
    return True


# --- Test 4: Integration test with FastAPI test client ---
def test_upload_endpoint():
    """Test the /upload endpoint processes images through rembg."""
    print("\n=== TEST 4: /upload endpoint integration test ===")
    
    from fastapi.testclient import TestClient
    import main
    
    # Patch SQLite to allow multi-threaded access for TestClient
    original_get_db_connection = main.get_db_connection
    def patched_get_db_connection():
        if main.DATABASE_URL:
            return original_get_db_connection()
        conn = sqlite3.connect(main.DATABASE_NAME, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    main.get_db_connection = patched_get_db_connection

    client = TestClient(app=main.app)

    # Create a test image
    img = Image.new("RGB", (200, 200), color=(255, 100, 50))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([50, 50, 150, 150], fill=(0, 100, 200))
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    print("  Uploading test image to /upload endpoint...")
    start = time.time()
    
    response = client.post(
        "/upload",
        files={"files": ("test_shirt.jpg", buf, "image/jpeg")},
        data={"user_id": "test_user"}
    )
    elapsed = time.time() - start
    
    print(f"  Response status: {response.status_code}")
    print(f"  Response time: {elapsed:.2f}s")
    
    data = response.json()
    print(f"  Response body: {data}")
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "items" in data, "Response should contain 'items'"
    assert len(data["items"]) == 1, "Should have 1 uploaded item"
    
    item = data["items"][0]
    assert "url" in item, "Item should have a 'url'"
    assert "id" in item, "Item should have an 'id'"
    
    # Verify the Cloudinary URL is a PNG (background removal outputs PNG)
    url = item["url"]
    print(f"  Cloudinary URL: {url}")
    assert ".png" in url.lower() or "f_png" in url.lower() or url.endswith("png"), \
        f"Expected PNG format in URL, got: {url}"
    
    # Restore original
    main.get_db_connection = original_get_db_connection
    
    print("  ✅ PASSED: Upload endpoint successfully processes and uploads cleaned images")
    return True


# --- Run all tests ---
if __name__ == "__main__":
    print("=" * 60)
    print("  Smart Background Cleanup — Test Suite")
    print("=" * 60)
    
    results = {}
    
    # Unit tests (no external dependencies needed)
    for test_fn in [
        test_remove_background_with_real_image,
        test_remove_background_with_corrupt_data,
        test_remove_background_with_empty_bytes,
        test_upload_endpoint,
    ]:
        name = test_fn.__name__
        try:
            results[name] = test_fn()
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            results[name] = False

    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("  🎉 All tests passed!")
    else:
        print("  ⚠️  Some tests failed. Check output above.")
        sys.exit(1)
