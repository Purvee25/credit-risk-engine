import React from "react";

/** Catches render errors so one throw doesn't blank the whole app. */
export default class ErrorBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Render error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="boot">
            <div className="boot-mark">◆</div>
            <p>Something went wrong. Try reloading the page.</p>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
