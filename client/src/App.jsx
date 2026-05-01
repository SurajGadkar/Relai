import Main from "./components/Main";
import "./App.css";

function App() {
  // AUTH BYPASSED — re-enable by restoring the token check from localStorage
  const token = localStorage.getItem("relai_token") || "dev_bypass";

  const handleSignOut = () => {
    localStorage.removeItem("relai_token");
    // When auth is re-enabled, set token to null here to show LoginPage
  };

  return (
    <div className="App">
      <Main token={token} onSignOut={handleSignOut} />
    </div>
  );
}

export default App;
