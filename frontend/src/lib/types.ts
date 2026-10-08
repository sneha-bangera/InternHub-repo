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

export interface ResumeProfile {
  id: string;
  user_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  links: string[];
}

export interface ResumeItem {
  id: string;
  profile_id: string;
}

export interface Education extends ResumeItem {
  institution: string;
  degree: string | null;
  field_of_study: string | null;
  start_date: string | null;
  end_date: string | null;
}

export interface ResumeProject extends ResumeItem {
  title: string;
  tech_stack: string[];
  bullets: string[];
  start_date: string | null;
  end_date: string | null;
  url: string | null;
}

export interface ResumeSkill extends ResumeItem {
  name: string;
  category: string | null;
  proficiency: string | null;
}

export interface ResumeCertificate extends ResumeItem {
  name: string;
  issuer: string | null;
  date: string | null;
  url: string | null;
}

export interface JobTarget {
  id: string;
  user_id: string;
  listing_id: string | null;
  company_name: string;
  role_title: string | null;
  seniority: string | null;
  jd_text: string;
  required_skills: string[];
  preferred_skills: string[];
  keywords: string[];
  created_at: string;
  updated_at: string;
}

export interface KeywordCoverage {
  score: number;
  matched_keywords: string[];
  missing_keywords: string[];
}

export interface RankedResumeItem<T> {
  item: T;
  score: number;
  matched_keywords: string[];
}

export interface ResumeSelection {
  projects: RankedResumeItem<ResumeProject>[];
  skills: RankedResumeItem<ResumeSkill>[];
  certificates: RankedResumeItem<ResumeCertificate>[];
  keyword_coverage: {
    before: KeywordCoverage;
    after: KeywordCoverage;
  };
}

export interface ResumeCompileJob {
  id: string;
  target_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  error: string | null;
  created_at: string;
  updated_at: string;
}

export type ResumeSections = Record<
  "contact" | "education" | "projects" | "skills" | "certificates",
  boolean
>;

export interface OverleafSnippet {
  snip_uri: string;
  snip_name: string;
}
