import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { api, Project, Scene } from '@/lib/api';
import StatusBadge from '@/components/StatusBadge';
import ProgressStepper from '@/components/ProgressStepper';
import SceneCard from '@/components/SceneCard';
import VideoPlayer from '@/components/VideoPlayer';
import { useProjectPolling } from '@/hooks/useProjectPolling';

export default function ProjectDetail() {
  const router = useRouter();
  const id = parseInt(router.query.id as string);
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);

  const shouldPoll = project ? ['draft', 'scripting', 'storyboarding', 'generating', 'composing', 'regenerating'].includes(project.status) : false;
  const { status: pollStatus } = useProjectPolling(id, shouldPoll);

  // Re-fetch project when poll status changes
  useEffect(() => {
    if (!id) return;
    api.getProject(id).then(setProject).catch(e => setError(e.message));
  }, [id, pollStatus]);

  const handleDelete = async () => {
    if (!confirm('Delete this project?')) return;
    await api.deleteProject(id);
    router.push('/');
  };

  const handleRegenerate = async () => {
    if (!confirm('Regenerate video from edited script?')) return;
    await api.regenerate(id);
  };

  if (error) return <div className="text-center py-20 text-red-500">{error}</div>;
  if (!project) return <div className="text-center py-20 text-gray-400">Loading...</div>;

  const isDone = project.status === 'done';
  const isFailed = project.status === 'failed';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{project.topic}</h1>
          <p className="text-sm text-gray-500">
            {project.duration}s &middot; {project.niche} &middot; {new Date(project.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={project.status} />
          <button onClick={handleDelete} className="text-xs text-red-400 hover:text-red-600">Delete</button>
        </div>
      </div>

      {/* Progress */}
      <ProgressStepper currentStatus={project.status} />

      {/* Error */}
      {isFailed && project.error_message && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
          {project.error_message}
        </div>
      )}

      {/* Video */}
      {isDone && (
        <VideoPlayer src={api.getVideoUrl(id)} title={project.topic} />
      )}

      {/* Cover */}
      {isDone && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Cover Image</h3>
          <img src={api.getCoverUrl(id)} alt="Cover" className="w-full max-w-sm rounded-lg border" />
        </div>
      )}

      {/* Script Review Link */}
      {project.script_json && (
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-medium">{project.script_json.title || 'Script'}</h3>
              <p className="text-sm text-gray-500">{project.script_json.scenes?.length || 0} scenes</p>
            </div>
            <Link href={`/projects/${id}/script`}
              className="text-indigo-600 hover:text-indigo-700 text-sm font-medium">
              Review & Edit
            </Link>
          </div>
        </div>
      )}

      {/* Scenes */}
      {project.scenes && project.scenes.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-3">Scenes ({project.scenes.length})</h3>
          <div className="grid gap-3">
            {project.scenes.map((scene: Scene, i: number) => (
              <SceneCard key={i} scene={scene} index={i} />
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      {(isDone || isFailed) && (
        <div className="flex gap-3">
          {isDone && (
            <a href={api.getVideoUrl(id)} download
              className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700">
              Download Video
            </a>
          )}
          {project.script_json && (
            <button onClick={handleRegenerate}
              className="border border-indigo-300 text-indigo-600 px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-50">
              Retry
            </button>
          )}
        </div>
      )}
    </div>
  );
}
