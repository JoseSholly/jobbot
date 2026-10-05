/** Shared types. Mirrors src/jobbot/domain/models.py on the Python side. */

export type UserStatus = "pending" | "active" | "paused" | "blocked";
export type FeedbackAction = "save" | "dismiss";

export interface User {
  chatId: number;
  username: string | null;
  firstName: string | null;
  status: UserStatus;
  isAdmin: boolean;
  ngQuota: number;
  globalQuota: number;
}

export interface Profile {
  target_titles: string[];
  skills: string[];
  seniority: string[];
  remote_ok: boolean;
  countries_ok: string[];
  exclude_keywords: string[];
  summary: string;
  /** Broader titles boards actually post ("Python Developer", "Virtual Assistant"). */
  related_titles: string[];
  /** Industries, e.g. fintech, e-commerce. */
  domains: string[];
}

export const DEFAULT_PROFILE: Profile = {
  target_titles: [],
  skills: [],
  seniority: [],
  remote_ok: true,
  countries_ok: ["Nigeria", "Worldwide", "Africa", "EMEA"],
  exclude_keywords: [],
  summary: "",
  related_titles: [],
  domains: [],
};

export interface Job {
  id: string;
  url: string;
  title: string;
  company: string;
  description: string;
  location: string;
}

/** Telegram user/chat info we care about. */
export interface Sender {
  chatId: number;
  username: string | null;
  firstName: string | null;
}

/** A reply produced by a service; handlers turn these into Telegram calls. */
export interface Reply {
  chatId: number;
  text: string;
  buttons?: { text: string; data: string }[][];
}
