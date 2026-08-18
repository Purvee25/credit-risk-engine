import React, { useState } from "react";
import { useStore } from "./store.js";

export default function Login() {
  const register = useStore((s) => s.register);
  const signIn = useStore((s) => s.signIn);

  const [mode, setMode] = useState("signin");   // "signin" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const isSignup = mode === "signup";

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isSignup) await register({ email, password, name });
      else await signIn({ email, password });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const swap = (next) => { setMode(next); setError(null); };

  return (
    <div className="login">
      <div className="login-orbs" aria-hidden />
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <span className="brand-mark" aria-hidden="true">◆</span>
          <div>
            <div className="brand-title">Credit Risk</div>
            <div className="brand-sub">Decision Engine</div>
          </div>
        </div>

        <div className="auth-tabs" role="tablist" aria-label="Sign in or create account">
          <button type="button" role="tab" aria-selected={!isSignup}
            className={!isSignup ? "active" : ""} onClick={() => swap("signin")}>
            Sign in
          </button>
          <button type="button" role="tab" aria-selected={isSignup}
            className={isSignup ? "active" : ""} onClick={() => swap("signup")}>
            Create account
          </button>
        </div>

        {isSignup && (
          <>
            <label htmlFor="auth-name">Full name</label>
            <input id="auth-name" type="text" value={name} autoComplete="name"
              onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" />
          </>
        )}

        <label htmlFor="auth-email">Work email</label>
        <input id="auth-email" type="email" value={email} required
          autoComplete={isSignup ? "email" : "username"}
          onChange={(e) => setEmail(e.target.value)} placeholder="you@lender.com" />

        <label htmlFor="auth-password">Password</label>
        <input id="auth-password" type="password" value={password} required
          autoComplete={isSignup ? "new-password" : "current-password"}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={isSignup ? "At least 8 characters" : "••••••••"} />

        {isSignup && (
          <p className="auth-hint">
            New accounts start as an <b>Analyst</b>. Override sign-off (Manager)
            is granted by an existing manager — it can't be self-assigned.
          </p>
        )}

        {error && <div className="auth-error" role="alert">{error}</div>}

        <button type="submit" disabled={busy}>
          {busy ? "Please wait…" : isSignup ? "Create account →" : "Sign in →"}
        </button>

        <p className="auth-switch">
          {isSignup ? "Already have an account? " : "New here? "}
          <button type="button" className="linklike"
            onClick={() => swap(isSignup ? "signin" : "signup")}>
            {isSignup ? "Sign in" : "Create one"}
          </button>
        </p>

        <div className="login-foot">Prototype — not for production lending decisions.</div>
      </form>
    </div>
  );
}
