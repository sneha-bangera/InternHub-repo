export interface User {
  id: string;
  email: string;
  full_name: string;
  whatsapp_number: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Listing {
  id: string;
  title: string;
  company: string;
  location: string | null;
  description: string | null;
  skills_required: string | null;
  stipend: string | null;
  duration: string | null;
  deadline: string | null;
  apply_url: string;
  source_platform: "internshala" | "linkedin" | "wellfound";
  is_active: boolean;
  created_at: string;
  updated_at: string;
  match_score?: number;
}

export interface ListingPage {
  items: Listing[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface UserSkill {
  id: string;
  user_id: string;
  skill: string;
  proficiency: "beginner" | "intermediate" | "advanced" | null;
  created_at: string;
}

export interface Application {
  id: string;
  user_id: string;
  listing_id: string;
  status: "saved" | "applied" | "rejected" | "accepted";
  match_score: number | null;
  notes: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
  listing: Listing;
}
