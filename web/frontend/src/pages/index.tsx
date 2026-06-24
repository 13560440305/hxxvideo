import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, Project } from '@/lib/api';
import ProjectCard from '@/components/ProjectCard';

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listProjects(50)
      .then(d => setProjects(d.projects))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-20 text-gray-400">Loading...</div>;
  if (error) return <div className="text-center py-20 text-red-500">Error: {error}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <Link href="/projects/new"
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors">
          + New Project
        </Link>
      </div>
      {projects.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-gray-400 mb-4">No projects yet</p>
          <Link href="/projects/new"
            className="text-indigo-600 hover:text-indigo-700 font-medium">
            Create your first project
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects.map(p => (
            <ProjectCard key={p.id} id={p.id} topic={p.topic} status={p.status}
              created_at={p.created_at} duration={p.duration} niche={p.niche} />
          ))}
        </div>
      )}
    </div>
  );
}
