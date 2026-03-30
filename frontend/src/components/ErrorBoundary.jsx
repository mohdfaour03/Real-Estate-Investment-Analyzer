import { Component } from "react";

/**
 * ErrorBoundary — catches render errors in child components so the
 * entire app doesn't crash. Shows a recovery UI with a retry button.
 *
 * Wrap around ChatPage (or any subtree) in main.jsx.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100vh",
            gap: "16px",
            padding: "24px",
            fontFamily: "'Inter', -apple-system, sans-serif",
            backgroundColor: "#0c0c12",
            color: "#e8e8ed",
          }}
        >
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "14px",
              background: "linear-gradient(135deg, #ef4444, #dc2626)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "20px",
              color: "white",
            }}
          >
            !
          </div>
          <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 600 }}>
            Something went wrong
          </h2>
          <p
            style={{
              color: "#8888a0",
              fontSize: "13px",
              maxWidth: "400px",
              textAlign: "center",
              lineHeight: "1.6",
            }}
          >
            An unexpected error occurred while rendering. This is usually
            caused by malformed data in a response.
          </p>
          <button
            onClick={this.handleReset}
            aria-label="Try again"
            style={{
              padding: "10px 24px",
              borderRadius: "10px",
              border: "1px solid #3b82f6",
              backgroundColor: "transparent",
              color: "#3b82f6",
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
              transition: "all 200ms ease",
            }}
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
