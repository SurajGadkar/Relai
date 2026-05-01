const BACKEND_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const handleGoogleLogin = () => {
    window.location.href = `${BACKEND_URL}/auth/google`;
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8">
      {/* Background decoration */}
      <div
        style={{
          position: "fixed",
          inset: 0,
          background:
            "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(99,102,241,0.12) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      {/* Logo */}
      <div className="text-center mb-10 relative">
        <h1 className="text-7xl font-black tracking-tighter text-indigo-600 italic">
          Rel.ai
        </h1>
        <p className="text-slate-400 font-semibold uppercase tracking-[0.25em] text-[10px] mt-2">
          Smart Wardrobe · v1.0
        </p>
      </div>

      {/* Card */}
      <div className="relative bg-white rounded-[2.5rem] shadow-2xl shadow-indigo-100/60 p-10 border border-indigo-50 w-full max-w-sm text-center">
        <div className="mb-8">
          <h2 className="text-2xl font-black tracking-tight text-slate-900">
            Welcome back
          </h2>
          <p className="text-slate-400 text-xs font-medium mt-2 leading-relaxed">
            Sign in to access your personal<br />AI-powered wardrobe
          </p>
        </div>

        <button
          onClick={handleGoogleLogin}
          className="w-full flex items-center justify-center gap-3 bg-white border-2 border-slate-200 hover:border-indigo-400 hover:shadow-lg hover:shadow-indigo-100 text-slate-700 py-4 rounded-2xl font-bold text-sm transition-all duration-200 active:scale-[0.97] group"
        >
          {/* Google Logo SVG */}
          <svg width="20" height="20" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M47.532 24.552c0-1.636-.132-3.2-.388-4.704H24.48v8.898h12.958c-.558 2.996-2.25 5.538-4.8 7.24v6.02h7.768c4.546-4.188 7.126-10.356 7.126-17.454z" fill="#4285F4"/>
            <path d="M24.48 48c6.498 0 11.946-2.15 15.928-5.834l-7.768-6.02c-2.15 1.44-4.9 2.288-8.16 2.288-6.274 0-11.59-4.234-13.49-9.926H2.954v6.218C6.918 42.662 15.1 48 24.48 48z" fill="#34A853"/>
            <path d="M10.99 28.508A14.53 14.53 0 0 1 10.23 24c0-1.568.27-3.088.76-4.508V13.274H2.954A23.96 23.96 0 0 0 .48 24c0 3.864.928 7.524 2.474 10.726l8.036-6.218z" fill="#FBBC05"/>
            <path d="M24.48 9.566c3.536 0 6.708 1.216 9.202 3.6l6.898-6.898C36.418 2.378 30.974 0 24.48 0 15.1 0 6.918 5.338 2.954 13.274l8.036 6.218c1.9-5.692 7.216-9.926 13.49-9.926z" fill="#EA4335"/>
          </svg>
          <span className="group-hover:text-indigo-700 transition-colors">Sign in with Google</span>
        </button>

        <p className="text-slate-300 text-[10px] font-medium mt-6 leading-relaxed">
          By signing in, you agree to let Rel.ai<br />curate your wardrobe experience.
        </p>
      </div>

      {/* Footer */}
      <p className="text-slate-300 text-[10px] font-medium mt-8 uppercase tracking-widest">
        Relai Engineering · v1.0.0
      </p>
    </div>
  );
}
