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
    return <p className="text-black/50">{loadingText}</p>;
  }

  if (isError) {
    return (
      <div className="bg-orange/10 border border-orange/30 text-orange text-sm px-4 py-3 rounded">
        {error?.message?.includes("Failed to fetch") || error?.message?.includes("NetworkError")
          ? "Cannot reach the API — make sure the backend is running on port 8000 and refresh the page."
          : error?.message || "Something went wrong loading data."}
      </div>
    );
  }

  return <>{children}</>;
}
