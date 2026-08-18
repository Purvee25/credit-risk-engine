import React, { useEffect, useState, Suspense, lazy } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import "./site.css";

// Lazy so the Three.js bundle isn't in the landing page's critical path.
const HeroCloud = lazy(() => import("./HeroCloud.jsx"));

/* ============================ Layout ============================ */
// Replace with your repository URL.
const GITHUB_URL = "https://github.com/your-username/credit-risk-engine";

const NAV = [];

function useTheme() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem("cr_theme") || "dark"
  );
  useEffect(() => localStorage.setItem("cr_theme", theme), [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

function Navbar({ theme, toggleTheme }) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <header className={`site-nav ${scrolled ? "scrolled" : ""}`}>
      <Link to="/" className="site-brand">
        <span className="brand-mark">◆</span>
        <span>Credit Risk <b>Engine</b></span>
      </Link>
      <nav className={`site-links ${open ? "open" : ""}`}>
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} onClick={() => setOpen(false)}>
            {n.label}
          </NavLink>
        ))}
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
        <Link to="/app" className="btn-primary sm" onClick={() => setOpen(false)}>
          Launch app →
        </Link>
      </nav>
      <button className="site-burger" onClick={() => setOpen((o) => !o)} aria-label="Menu">
        ☰
      </button>
    </header>
  );
}

function Footer() {
  return (
    <footer className="site-footer">
      <div className="foot-cols">
        <div>
          <div className="site-brand">
            <span className="brand-mark">◆</span>
            <span>Credit Risk <b>Engine</b></span>
          </div>
          <p className="foot-tag">
            Fairer credit decisions through behavioral intelligence.
          </p>
        </div>
        <div>
          <h4>Explore</h4>
          {NAV.map((n) => <Link key={n.to} to={n.to}>{n.label}</Link>)}
          <Link to="/app">Launch app</Link>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer noopener">GitHub ↗</a>
        </div>
        <div>
          <h4>Built with</h4>
          <span>Python · scikit-learn · XGBoost</span>
          <span>SHAP · FastAPI</span>
          <span>React · Three.js</span>
        </div>
      </div>
      <div className="foot-bar">
        <span>Prototype for demonstration — not validated for production lending decisions.</span>
      </div>
    </footer>
  );
}

export function SiteLayout() {
  const { pathname } = useLocation();
  const [theme, toggleTheme] = useTheme();
  useEffect(() => window.scrollTo(0, 0), [pathname]);

  // Scroll-reveal: animate sections in as they enter the viewport. Progressive
  // enhancement — if JS/observer is unavailable, content stays fully visible.
  useEffect(() => {
    const els = document.querySelectorAll(
      ".sect, .cta-band, .stat-band, .page-head, .faq, .contact, .preview-band, .why, .how"
    );
    els.forEach((e) => e.classList.add("reveal"));
    const io = new IntersectionObserver(
      (entries) => entries.forEach((en) => {
        if (en.isIntersecting) {
          en.target.classList.add("in");
          io.unobserve(en.target);
        }
      }),
      { threshold: 0.12 }
    );
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, [pathname]);
  return (
    <div className="site" data-theme={theme}>
      <Navbar theme={theme} toggleTheme={toggleTheme} />
      <main><Outlet /></main>
      <Footer />
    </div>
  );
}

/* ========================= Reusable bits ========================= */
function Section({ kicker, title, sub, children, className = "" }) {
  return (
    <section className={`sect ${className}`}>
      {kicker && <div className="kicker">{kicker}</div>}
      {title && <h2 className="sect-title">{title}</h2>}
      {sub && <p className="sect-sub">{sub}</p>}
      {children}
    </section>
  );
}

function Feature({ icon, title, body }) {
  return (
    <div className="feature">
      <div className="feature-ico">{icon}</div>
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}

function Stat({ value, label, accent }) {
  return (
    <div className="stat-tile">
      <div className="stat-value" style={accent ? { color: "var(--accent)" } : null}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

/* A real, static preview of the dashboard UI — not a stock screenshot. */
function ProductPreview() {
  const rows = [
    ["Payment consistency", -13, "lo"],
    ["Income volatility", -7, "lo"],
    ["Debt trend", 4, "hi"],
  ];
  return (
    <div className="preview-frame" aria-hidden="true">
      <div className="preview-chrome">
        <span className="dot r" /><span className="dot y" /><span className="dot g" />
        <span className="preview-url">creditrisk.app/portfolio</span>
      </div>
      <div className="preview-body">
        <div className="preview-kpis">
          <div className="pk"><span>Applicants</span><b>250</b></div>
          <div className="pk"><span>Avg risk</span><b>40.2%</b></div>
          <div className="pk accent"><span>Approval</span><b>40%</b></div>
        </div>
        <div className="preview-shap">
          {rows.map(([label, v, cls]) => (
            <div className="pv-row" key={label}>
              <span>{label}</span>
              <div className="pv-track">
                <div className={`pv-bar ${cls}`} style={{ width: `${Math.abs(v) * 4}px`, marginLeft: v < 0 ? "auto" : 0 }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CTA() {
  return (
    <section className="cta-band">
      <h2>See the models make a decision.</h2>
      <p>250 live applicants, one dashboard — score, explain, and flip decisions in real time.</p>
      <Link to="/app" className="btn-primary">Launch the app →</Link>
    </section>
  );
}

const FEATURES = [
  ["📈", "Behavioral scoring", "Blends traditional credit data with payment consistency, income volatility, and debt trend to rate thin-file borrowers a conventional score can't."],
  ["🔍", "Explainable by design", "Every decision comes with a SHAP breakdown in plain risk-percentage terms — which features raised or lowered the score."],
  ["⚖️", "Fairness lens", "Approval-rate analysis across income brackets surfaces access gaps before they become bias."],
  ["⚡", "Real-time API", "A FastAPI backend scores applicants and returns explanations in milliseconds — upload a CSV or POST a batch."],
  ["🌐", "Risk Map", "A visual map of the whole portfolio — higher means riskier, colour shows the decision — alongside the main table, pipeline, and reports."],
  ["🔄", "Decision flips", "See exactly which applicants the traditional model rejects but behavioral data approves — the core of financial inclusion."],
];

const FAQS = [
  ["Is this usable for real lending?", "No — it's a prototype on synthetic data, not validated for production lending. Every surface carries that disclaimer."],
  ["Why AUC-PR instead of accuracy?", "Defaults are the rare class (~22%). Accuracy is misleading; AUC-PR measures how well the model separates defaulters from non-defaulters."],
  ["How much do behavioral features help?", "Best-model AUC-PR rises 0.52 → 0.67 on the held-out test set — the magnitude is illustrative (synthetic), not a market estimate."],
  ["Does the site need the backend?", "No. It falls back to a bundled snapshot; live scoring and CSV upload require the FastAPI backend."],
];

function FAQSection() {
  return (
    <section className="faq">
      <div className="kicker">FAQ</div>
      <h2 className="sect-title">Questions, answered.</h2>
      <div className="faq-list">
        {FAQS.map(([q, a]) => (
          <details key={q}>
            <summary>{q}</summary>
            <p>{a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function Contact() {
  return (
    <section className="contact">
      <div className="kicker">Get the code</div>
      <h2 className="sect-title">Explore it, or run it yourself.</h2>
      <p className="contact-sub">
        Open-source prototype — clone the repo, launch the live demo, or read the docs.
      </p>
      <div className="contact-cta">
        <a className="btn-primary" href={GITHUB_URL} target="_blank" rel="noreferrer noopener">
          View on GitHub ↗
        </a>
        <Link className="btn-ghost" to="/app">Launch live demo →</Link>
      </div>
    </section>
  );
}

/* ============================ Pages ============================ */
export function Landing() {
  return (
    <>
      <section className="hero">
        <Suspense fallback={<div className="hero-field" aria-hidden />}>
          <HeroCloud />
        </Suspense>
        <div className="hero-inner">
          <div className="pill">Behavioral credit intelligence</div>
          <h1 className="hero-title">Credit risk,<br /><span className="accent">re-scored.</span></h1>
          <p className="hero-lead">
            Fairer lending for the thin-file borrowers a traditional score can't see.
          </p>
          <div className="hero-cta">
            <Link to="/app" className="btn-primary lg">Launch demo →</Link>
            <a className="btn-ghost lg" href={GITHUB_URL} target="_blank" rel="noreferrer noopener">
              GitHub ↗
            </a>
          </div>
        </div>
        <div className="hero-scroll" aria-hidden="true">Scroll to explore</div>
      </section>

      {/* Product preview — show, don't explain */}
      <section className="preview-band reveal">
        <div className="preview-copy">
          <div className="kicker">Live demo</div>
          <h2 className="sect-title">See the model decide.</h2>
          <p className="demo-lead">Drag one threshold. Watch 250 applicants get approved or declined, live.</p>
          <div className="preview-stats">
            <div><b>0.67</b><span>AUC-PR</span></div>
            <div><b>+35</b><span>rescued</span></div>
            <div><b>82%</b><span>recall</span></div>
          </div>
          <Link to="/app" className="btn-primary">Open the dashboard →</Link>
        </div>
        <ProductPreview />
      </section>

      {/* Why it's better — alternating editorial rows */}
      <section className="why reveal">
        <div className="kicker">Why it's better</div>
        <div className="why-rows">
          {[
            ["↔", "Decision flips", "Approve the thin-file borrowers a traditional model rejects — the whole point of behavioral data."],
            ["◎", "Explainable", "Every score ships with a SHAP breakdown in plain risk percentage. No black box."],
            ["⚖", "Fair by design", "Approval access is checked across income brackets before it becomes bias."],
          ].map(([ico, t, b], i) => (
            <div className={`why-row ${i % 2 ? "rev" : ""}`} key={t}>
              <span className="why-ico-lg" aria-hidden="true">{ico}</span>
              <div>
                <h3>{t}</h3>
                <p>{b}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* How the AI works — timeline */}
      <section className="how reveal">
        <div className="kicker">How the AI works</div>
        <div className="timeline">
          {[
            ["Data", "Synthetic, honest by design"],
            ["Features", "Traditional + behavioral"],
            ["Model", "LR · RF · XGBoost"],
            ["Explain", "SHAP in risk %"],
          ].map(([t, b], i) => (
            <div className="tl-step" key={t}>
              <span className="tl-dot">{String(i + 1).padStart(2, "0")}</span>
              <h4>{t}</h4>
              <p>{b}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Results */}
      <div className="stat-band reveal">
        <Stat value="+0.15" label="AUC-PR gain from behavioral data" accent />
        <Stat value="0.67" label="Best-model AUC-PR" />
        <Stat value="82%" label="Defaulters caught (recall)" />
        <Stat value="5,000" label="Applicants modeled" />
      </div>

      <FAQSection />
      <Contact />
    </>
  );
}
