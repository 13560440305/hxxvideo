import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { api, Scene } from '@/lib/api';
import ScriptEditor from '@/components/ScriptEditor';

export default function ScriptPage() {
  const router = useRouter();
  const id = parseInt(router.query.id as string);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getScript(id)
      .then(s => {
        setTitle(s.title || '');
        setDescription(s.description || '');
        setScenes(s.scenes || []);
      })
      .catch(e => setError(e.message));
  }, [id]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.updateScript(id, scenes);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setError(e.message);
    }
    setSaving(false);
  };

  const handleRegenerate = async () => {
    if (!confirm('This will regenerate the video with edited script. Continue?')) return;
    try {
      await api.updateScript(id, scenes);
      await api.regenerate(id);
      router.push(`/projects/${id}`);
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (error) return <div className="text-center py-20 text-red-500">{error}</div>;
  if (!scenes.length) return <div className="text-center py-20 text-gray-400">Loading script...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Edit Script</h1>
        <div className="flex gap-2">
          <button onClick={handleSave} disabled={saving}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save'}
          </button>
          <button onClick={handleRegenerate}
            className="border border-indigo-300 text-indigo-600 px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-50">
            Save & Regenerate
          </button>
        </div>
      </div>

      <ScriptEditor title={title} description={description} scenes={scenes} onChange={setScenes} />
    </div>
  );
}
