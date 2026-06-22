import type { ReactNode } from "react";

interface Props {
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  loadingText?: string;
  children: ReactNode;
}

export function QueryStatus({
  isLoading,
  isError,
  error,
  loadingText = "Loading…",
  children,
}: Props) {
  if (isLoading) {
    return <p className="text-muted">{loadingText}</p>;
  }

  if (isError) {
    return (
      <div className="bg-warning/10 border border-warning/30 text-warning text-sm px-4 py-3 rounded">
        {error?.message?.includes("Failed to fetch") || error?.message?.includes("NetworkError")
          ? "Cannot reach the API — make sure the backend is running on port 8000 and refresh the page."
          : error?.message || "Something went wrong loading data."}
      </div>
    );
  }

  return <>{children}</>;
}
