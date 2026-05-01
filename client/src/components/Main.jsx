import { useState, useEffect } from "react";

// Use environment variable or fallback to local
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Main({ token, onSignOut }) {
  const [vibe, setVibe] = useState("Casual");
  const [suggestion, setSuggestion] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");

  const authHeaders = { Authorization: `Bearer ${token}` };

  const fetchItems = async () => {
    try {
      const res = await fetch(`${API_BASE}/items`, { headers: authHeaders });
      const data = await res.json();
      setItems(data);
    } catch (err) {
      console.error("Failed to fetch items from backend.", err);
    }
  };

  // Fetch closet items on load
  useEffect(() => {
    fetchItems();
  }, []);


  const handleBulkUpload = async (event) => {
    const selectedFiles = event.target.files; // This is a FileList
    if (!selectedFiles.length) return;

    setIsUploading(true);
    const formData = new FormData();

    // SDE 2 Tip: Append each file to the SAME key "files"
    // This matches the List[UploadFile] in your FastAPI backend
    for (let file of selectedFiles) {
      formData.append("files", file);
    }

    // user_id is derived from the JWT on the backend — no need to send it

    try {
      const response = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        headers: authHeaders,
        body: formData,
      });

      const data = await response.json();
      console.log("Upload queued:", data);

      // Refresh the closet to see the "Processing..." items
      fetchItems();
    } catch (error) {
      console.error("Upload failed:", error);
    } finally {
      setIsUploading(false);
    }
  };

  const getSuggestion = async () => {
    setLoading(true);
    setError("");
    setSuggestion(null);
    try {
      const res = await fetch(`${API_BASE}/suggest?weather=sunny&vibe=${vibe}`, { headers: authHeaders });
      const data = await res.json();

      if (data.error) {
        setError(data.error);
      } else {
        // Adapt to the new schema from GEMINI.md
        if (data.recommendation) {
            setSuggestion([
                { ...data.recommendation, rank: 1 }
            ]);
        } else {
            setSuggestion(data.suggestions || []);
        }
      }
    } catch (err) {
      setError(
        "Stylist is offline. Check if your Local LLM/LM Studio is running.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 p-4 pb-10 font-sans selection:bg-indigo-100">
      {/* CSS for hiding scrollbars while keeping functionality */}
      <style>{`
        /* Default: Show scrollbars for laptop/desktop users */
        .hide-scrollbar {
          scrollbar-width: auto;
          -ms-overflow-style: auto;
        }

        /* Only hide scrollbars on touch devices (Mobile/Tablets) */
        @media (hover: none) and (pointer: coarse) {
          .hide-scrollbar::-webkit-scrollbar { 
            display: none; 
          }
          .hide-scrollbar { 
            scrollbar-width: none; 
            -ms-overflow-style: none; 
          }
        }
      `}</style>

      {/* Header */}
      <header className="max-w-md mx-auto pt-6 pb-2 flex items-center justify-between">
        <div className="text-left">
          <h1 className="text-4xl font-black tracking-tighter text-indigo-600 italic">Rel.ai</h1>
          <p className="text-slate-400 font-medium uppercase tracking-widest text-[10px] mt-0.5">
            Smart Wardrobe v1.0
          </p>
        </div>
        <button
          onClick={onSignOut}
          className="text-[10px] font-black text-slate-400 hover:text-red-500 uppercase tracking-widest transition-colors border border-slate-200 hover:border-red-200 px-3 py-2 rounded-xl"
        >
          Sign Out
        </button>
      </header>

      <main className="max-w-md mx-auto space-y-8">
        {/* Suggestion Card */}
        <section className="bg-white rounded-[2.5rem] shadow-2xl shadow-indigo-100/50 p-8 border border-indigo-50">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold tracking-tight">Today's Fit</h2>
            <span className="bg-indigo-100 text-indigo-700 text-[10px] font-black px-3 py-1 rounded-full uppercase">
              30°C BLR
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 mb-8">
            {["Casual", "Office", "Date"].map((v) => (
              <button
                key={v}
                onClick={() => setVibe(v)}
                className={`py-3 rounded-2xl text-xs font-bold transition-all active:scale-95 ${
                  vibe === v
                    ? "bg-indigo-600 text-white shadow-lg shadow-indigo-200"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {v}
              </button>
            ))}
          </div>

          <button
            onClick={getSuggestion}
            disabled={loading}
            className="w-full bg-slate-900 hover:bg-black text-white py-5 rounded-2xl font-black text-sm uppercase tracking-wider transition-all disabled:opacity-50 active:scale-[0.98]"
          >
            {loading ? "Curating your look..." : "Ask the Stylist"}
          </button>

          {error && (
            <div className="mt-8 p-6 bg-red-50 border border-red-100 rounded-[2rem] text-center animate-in fade-in zoom-in duration-300">
              <span className="text-2xl">⚠️</span>
              <h3 className="text-red-800 font-bold mt-2">Stylist is Busy</h3>
              <p className="text-red-500 text-[10px] font-medium mt-1 leading-relaxed px-4">
                {error}
              </p>
              <button
                onClick={getSuggestion}
                className="mt-3 text-[10px] font-black text-red-700 underline uppercase tracking-tighter"
              >
                Try Again
              </button>
            </div>
          )}

          {suggestion && <OutfitSuggestion items = {items} suggestion={suggestion} />}
        </section>

        {/* Closet Gallery */}
        <section>
          <div className="flex justify-between items-end mb-6 px-2">
            <h3 className="text-lg font-bold tracking-tight">Your Closet</h3>
            <label className="bg-indigo-50 text-indigo-600 px-4 py-2 rounded-full font-bold text-xs cursor-pointer hover:bg-indigo-100 transition-colors">
              {isUploading ? "AI Identifying..." : "+ Add Item"}
              <input
                type="file"
                multiple
                className="hidden"
                accept="image/*"
                onChange={handleBulkUpload}
                disabled={isUploading}
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {items.length > 0 ? (
              items.map((item) => (
                <div
                  key={item.id}
                  className="group relative bg-white rounded-3xl overflow-hidden shadow-sm border border-slate-100"
                >
                  <img
                    src={item.image_path}
                    alt={item.tags}
                    className="w-full aspect-[4/5] object-cover transition-transform duration-700 group-hover:scale-110"
                  />
                  <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 via-black/20 to-transparent">
                    <p className="text-white text-[10px] font-black truncate uppercase tracking-widest">
                      {item.tags || "Processing..."}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-2 py-16 text-center border-2 border-dashed border-slate-200 rounded-[2.5rem]">
                <p className="text-slate-400 text-xs font-medium">
                  Your closet is empty.
                  <br />
                  Upload your first fit! 📸
                </p>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

const getItemPath = (items, id) => {
    // Find the item in your local 'closet' state
    const item = items.find((i) => i.id === id);

    if (!item) return "/placeholder-image.jpg"; // Fallback if ID is missing
    
    return item.image_path;
  };

const OutfitSuggestion = ({ items, suggestion }) => {
  console.log("Suggestions ->", suggestion);
  if (!suggestion || suggestion.length === 0) {
    return (
      <div className="mt-8 p-8 bg-slate-50 rounded-[2rem] text-center border-2 border-dashed border-slate-200">
        <p className="text-slate-500 text-[11px] font-bold uppercase tracking-widest leading-loose">
          The stylist couldn't find a perfect match. <br /> Try adding more
          clothes or changing the vibe! ☕
        </p>
      </div>
    );
  }

  return (
    <div className="mt-8 animate-in fade-in slide-in-from-bottom-6 duration-1000 ease-out">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-black text-slate-900 uppercase tracking-widest">
          The Perfect Match
        </h2>
        <span className="text-[10px] bg-slate-900 text-white font-black px-2 py-0.5 rounded italic">
          {suggestion.length} ITEMS
        </span>
      </div>

      <div className="flex gap-6 overflow-x-auto pb-8 snap-x snap-mandatory hide-scrollbar">
        {suggestion?.map((outfit) => (
          <div
            key={outfit.rank}
            className="flex-none w-80 snap-center bg-white rounded-[3rem] p-4 border border-slate-100 shadow-2xl shadow-indigo-100/30"
          >
            {/* Header: Score & Logic */}
            <div className="flex justify-between items-center mb-4 px-2">
              <div className="flex flex-col">
                <span className="text-[10px] font-black text-indigo-500 uppercase tracking-widest">
                  Option {outfit.rank}
                </span>
                <span className="text-xs font-bold text-slate-400 italic">
                  {outfit.outfit_name || outfit.logic || outfit.items?.logic || "Balanced Palette"}
                </span>
              </div>
              <div className="bg-indigo-600 text-white px-3 py-1 rounded-full text-sm font-black shadow-lg shadow-indigo-200">
                {outfit.confidence_score || outfit.style_score}
              </div>
            </div>

            {/* Internal Item Grid */}
            <div className="grid grid-cols-2 gap-2 mb-4">
              {[
                outfit.items?.base_layer,
                outfit.items?.mid_layer,
                outfit.items?.outerwear,
                outfit.items?.top,
                outfit.items?.bottom,
                outfit.items?.shoes,
                outfit.items?.footwear,
                ...(Array.isArray(outfit.items?.accessories) ? outfit.items.accessories : [])
              ]
                .filter(Boolean)
                .map((item, idx) => {
                  const itemId = typeof item === "string" ? item : item.id;
                  return (
                  <div key={itemId || idx} className="relative group">
                    <img
                      src={getItemPath(items, itemId)}
                      className="w-full aspect-square object-cover rounded-[1.5rem] bg-slate-50 border border-slate-100"
                      alt="Clothing item"
                    />
                  </div>
                )})}
            </div>

            {/* Stylist Reasoning Section */}
            <div className="bg-slate-50 rounded-[2.5rem] p-5 border border-slate-100">
              <span className="block text-[10px] font-black text-slate-400 uppercase mb-2 tracking-widest">
                Stylist Notes
              </span>
              <p className="text-[11px] leading-relaxed font-medium text-slate-600 ">
                {outfit.rationale || outfit.reasoning || outfit.items?.reasoning}
              </p>
            </div>
          </div>
        ))}
      </div>
      <button className="w-full mt-4 py-4 bg-indigo-600 text-white rounded-2xl font-black text-xs uppercase tracking-[0.2em] shadow-xl shadow-indigo-200 active:scale-95 transition-all">
        Lock this Fit
      </button>
    </div>
  );
};
