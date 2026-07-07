/** Brand locations shown in Generate Content (maps to backend brand_id). */
export interface BrandLocation {
  id: string;
  brandId: string;
  name: string;
  address: string;
  city: string;
  state: string;
}

export const BRAND_LOCATIONS: BrandLocation[] = [
  {
    id: "ameritex_san_antonio",
    brandId: "ameritex",
    name: "AmeriTex Elevator Services",
    address: "12050 Crownpoint Dr #140, San Antonio, Texas",
    city: "San Antonio",
    state: "TX",
  },
  {
    id: "ameritex_hayward",
    brandId: "ameritex",
    name: "AmeriTex Elevator West",
    address: "3454 Depot Rd, Hayward, California",
    city: "Hayward",
    state: "CA",
  },
  {
    id: "arizona_es_tempe",
    brandId: "arizona_es",
    name: "Arizona Elevator Solutions",
    address: "208 S River Dr, Tempe, Arizona",
    city: "Tempe",
    state: "AZ",
  },
  {
    id: "arizona_es_tucson",
    brandId: "arizona_es",
    name: "Arizona Elevator Solutions",
    address: "Tucson, Tucson, Arizona",
    city: "Tucson",
    state: "AZ",
  },
  {
    id: "axxiom_pompano",
    brandId: "axxiom",
    name: "Axxiom Elevator Florida",
    address: "2101 W Atlantic Blvd STE 104, Pompano Beach, FL",
    city: "Pompano Beach",
    state: "FL",
  },
  {
    id: "axxiom_florida",
    brandId: "axxiom",
    name: "Axxiom Elevator Florida",
    address: "2101 W Atlantic Blvd, Pompano Beach, FL",
    city: "Pompano Beach",
    state: "FL",
  },
  {
    id: "axxiom_southeast",
    brandId: "axxiom",
    name: "Axxiom Elevator Southeast",
    address: "6222 Clarity Ct, Sarasota, FL",
    city: "Sarasota",
    state: "FL",
  },
  {
    id: "liftech_signal_hill",
    brandId: "liftech",
    name: "Liftech Elevator Services LLC",
    address: "2897 Gardena Ave, Signal Hill, California",
    city: "Signal Hill",
    state: "CA",
  },
  {
    id: "quality_bladensburg",
    brandId: "quality",
    name: "Quality Elevator Co LLC",
    address: "4808 Upshur St, Bladensburg, Maryland",
    city: "Bladensburg",
    state: "MD",
  },
];

export function locationInitial(name: string): string {
  const letter = name.trim().charAt(0).toUpperCase();
  return letter || "?";
}
