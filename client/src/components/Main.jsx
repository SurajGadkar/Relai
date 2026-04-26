import React, { useState, useEffect } from 'react';

const API_BASE = "http://localhost:8000";

export default function Main() {
  const [vibe, setVibe] = useState('Casual');
  const [suggestion, setSuggestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [items, setItems] = useState([]);

  // Fetch closet items on load
  useEffect(() => {
    fetchItems();
  }, []);

  const fetchItems = async () => {
    try {
      const res = await fetch(`${API_BASE}/items`); // You'll need to add this endpoint in FastAPI
      const data = await res.json();
      setItems(data);
    } catch (err) {
      console.error("Failed to fetch items");
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const tags = prompt("What is this? (e.g., 'Beige Chinos', 'Navy Polo')");
    if (!tags) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('tags', tags);

    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        alert("Added to closet!");
        fetchItems(); // Refresh the list
      }
    } catch (err) {
      alert("Upload failed. Check backend.");
    } finally {
      setIsUploading(false);
    }
  };

  const getSuggestion = async () => {
    setLoading(true);
    setSuggestion("");
    try {
      // Sending hardcoded Bangalore weather for now
      const res = await fetch(`${API_BASE}/suggest?weather=sunny&vibe=${vibe}`);
      const data = await res.json();
      setSuggestion(data.suggestion);
    } catch (err) {
      setSuggestion("Stylist is offline. Check if your Local LLM is running.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 p-4 pb-10 font-sans">
      {/* Header */}
      <header className="max-w-md mx-auto pt-6 pb-10 text-center">
        <h1 className="text-5xl font-black tracking-tighter text-indigo-600 italic">Rel.ai</h1>
        <p className="text-slate-400 font-medium uppercase tracking-widest text-[10px] mt-1">Smart Wardrobe v1.0</p>
      </header>

      <main className="max-w-md mx-auto space-y-8">
        {/* Suggestion Card */}
        <section className="bg-white rounded-[2rem] shadow-2xl shadow-indigo-100 p-8 border border-indigo-50">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold">Today's Fit</h2>
            <span className="bg-indigo-100 text-indigo-700 text-[10px] font-bold px-3 py-1 rounded-full uppercase">30°C BLR</span>
          </div>

          <div className="grid grid-cols-3 gap-2 mb-8">
            {['Casual', 'Office', 'Date'].map((v) => (
              <button 
                key={v}
                onClick={() => setVibe(v)}
                className={`py-3 rounded-2xl text-xs font-bold transition-all ${
                  vibe === v ? 'bg-indigo-600 text-white shadow-lg scale-105' : 'bg-slate-100 text-slate-500'
                }`}
              >
                {v}
              </button>
            ))}
          </div>

          <button 
            onClick={getSuggestion}
            disabled={loading}
            className="w-full bg-slate-900 hover:bg-black text-white py-5 rounded-2xl font-black text-sm uppercase tracking-wider transition-all disabled:opacity-50"
          >
            {loading ? "Analyzing Wardrobe..." : "Ask the Stylist"}
          </button>

          {suggestion && (
            <div className="mt-8 p-5 bg-indigo-50 rounded-2xl border-l-4 border-indigo-600 animate-in fade-in slide-in-from-top-4">
              <p className="text-indigo-950 text-sm leading-relaxed font-medium">{suggestion}</p>
            </div>
          )}
        </section>

        {/* Closet Gallery */}
        <section>
          <div className="flex justify-between items-end mb-4 px-2">
            <h3 className="text-lg font-bold">Your Closet</h3>
            <label className="text-indigo-600 font-bold text-sm cursor-pointer hover:underline">
              {isUploading ? "Uploading..." : "+ Add Item"}
              <input type="file" className="hidden" accept="image/*" capture="environment" onChange={handleUpload} />
            </label>
          </div>
          
          <div className="grid grid-cols-3 gap-3">
            {items.length > 0 ? items.map((item, i) => (
              <div key={i} className="aspect-square bg-white rounded-2xl overflow-hidden shadow-sm border border-slate-100">
                <img 
                  src={`${API_BASE}/${item.image_path}`} 
                  alt={item.tags} 
                  className="w-full h-full object-cover"
                />
              </div>
            )) : (
              <div className="col-span-3 py-10 text-center border-2 border-dashed border-slate-200 rounded-3xl">
                <p className="text-slate-400 text-xs">No clothes found. Start by adding one!</p>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}