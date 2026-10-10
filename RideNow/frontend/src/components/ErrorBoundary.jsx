import { Component } from 'react';

export class ErrorBoundary extends Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('RideNow UI Uncaught Exception:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#06090E] text-[#F5F7FA] flex items-center justify-center p-6">
          <div className="max-w-md w-full p-8 rounded-2xl bg-[#0D1520] border border-red-500/30 text-center space-y-4 shadow-2xl">
            <div className="w-12 h-12 mx-auto rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 text-xl font-bold">
              !
            </div>
            <h2 className="text-xl font-bold tracking-tight text-white">Interface Interrupted</h2>
            <p className="text-xs text-gray-400 leading-relaxed">
              RideNow encountered an unexpected UI rendering error. Your data and rides are safely stored on the server.
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="w-full py-2.5 rounded-xl bg-[#38BDF8] hover:bg-[#38BDF8]/90 text-black font-semibold text-xs tracking-wider uppercase transition-all shadow-lg shadow-[#38BDF8]/20"
            >
              Reload Interface
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
