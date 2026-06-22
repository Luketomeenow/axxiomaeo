import { BRAND_LOCATIONS, locationInitial, type BrandLocation } from "../data/brandLocations";

function PinIcon() {
  return (
    <svg
      className="w-4 h-4 text-muted/40 shrink-0"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden
    >
      <path d="M12 21s7-4.5 7-10a7 7 0 1 0-14 0c0 5.5 7 10 7 10z" />
      <circle cx="12" cy="11" r="2.5" />
    </svg>
  );
}

interface BrandLocationPickerProps {
  selectedId: string;
  onSelect: (location: BrandLocation) => void;
}

export function BrandLocationPicker({ selectedId, onSelect }: BrandLocationPickerProps) {
  return (
    <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
      {BRAND_LOCATIONS.map((location) => {
        const selected = selectedId === location.id;
        return (
          <button
            key={location.id}
            type="button"
            onClick={() => onSelect(location)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border text-left transition-colors ${
              selected
                ? "border-navy bg-navy/5 ring-1 ring-navy/20"
                : "border-black/10 hover:border-black/20 hover:bg-black/[0.02]"
            }`}
          >
            <span
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                selected ? "bg-cyan text-void" : "bg-black/8 text-muted"
              }`}
            >
              {locationInitial(location.name)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-ink truncate">{location.name}</span>
              <span className="block text-xs text-muted truncate">{location.address}</span>
            </span>
            <PinIcon />
          </button>
        );
      })}
    </div>
  );
}
