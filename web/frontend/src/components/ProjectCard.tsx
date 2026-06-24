import Link from 'next/link';
import StatusBadge from './StatusBadge';

interface ProjectCardProps {
  id: number;
  topic: string;
  status: string;
  created_at: string;
  duration: number;
  niche: string;
}

export default function ProjectCard({ id, topic, status, created_at, duration, niche }: ProjectCardProps) {
  return (
    <Link href={`/projects/${id}`} className="block bg-white rounded-lg border border-gray-200 p-5 hover:shadow-md hover:border-indigo-300 transition-all">
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-semibold text-gray-900 truncate flex-1 mr-2">{topic}</h3>
        <StatusBadge status={status} />
      </div>
      <div className="text-sm text-gray-500 space-y-1">
        <p>{duration}s &middot; {niche}</p>
        <p>{new Date(created_at).toLocaleString()}</p>
      </div>
    </Link>
  );
}
