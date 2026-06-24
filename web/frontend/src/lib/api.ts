const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

export interface Project {
  id: number;
  topic: string;
  niche: string;
  duration: number;
  format: string;
  status: string;
  output_path?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
  script_json?: Script;
  storyboard_json?: any;
  scenes?: Scene[];
  cover_path?: string;
}

export interface Script {
  title: string;
  description: string;
  scenes: Scene[];
}

export interface Scene {
  id: number;
  duration: number;
  zh_narration: string;
  en_narration: string;
  visual_prompt: string;
  shot_type: string;
  expanded_visual_prompt?: string;
  camera_movement?: string;
  lighting?: string;
  key_elements?: string[];
}

export interface Niche {
  name: string;
  description: string;
  file: string;
}

export interface StatusInfo {
  id: number;
  status: string;
  updated_at: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  return res.json();
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  listProjects: (limit = 20, offset = 0, status?: string) =>
    request<{ projects: Project[]; total: number }>(
      `/projects?limit=${limit}&offset=${offset}${status ? `&status=${status}` : ''}`
    ),

  createProject: (data: {
    topic: string;
    niche?: string;
    duration?: number;
    fmt?: string;
    resolution?: string;
    bg_music?: string;
    skip_video?: boolean;
  }) =>
    request<{ project_id: number; status: string }>('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getProject: (id: number) => request<Project>(`/projects/${id}`),

  getProjectStatus: (id: number) => request<StatusInfo>(`/projects/${id}/status`),

  deleteProject: (id: number) => request<{ ok: boolean }>(`/projects/${id}`, { method: 'DELETE' }),

  getScript: (id: number) => request<Script>(`/projects/${id}/script`),

  updateScript: (id: number, scenes: Scene[]) =>
    request<{ ok: boolean }>(`/projects/${id}/script`, {
      method: 'PUT',
      body: JSON.stringify({ scenes }),
    }),

  regenerate: (id: number) =>
    request<{ project_id: number; status: string }>(`/projects/${id}/regenerate`, { method: 'POST' }),

  listNiches: () => request<{ niches: Niche[] }>('/niches'),

  getVideoUrl: (id: number) => `${API_BASE}/projects/${id}/video`,

  getCoverUrl: (id: number) => `${API_BASE}/projects/${id}/cover`,
};
