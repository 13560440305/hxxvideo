const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-200 text-gray-700',
  scripting: 'bg-blue-100 text-blue-700',
  storyboarding: 'bg-indigo-100 text-indigo-700',
  generating: 'bg-yellow-100 text-yellow-700',
  composing: 'bg-orange-100 text-orange-700',
  done: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  draft_ready: 'bg-purple-100 text-purple-700',
  regenerating: 'bg-indigo-100 text-indigo-700',
};

const STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  scripting: 'Scripting',
  storyboarding: 'Storyboard',
  generating: 'Generating',
  composing: 'Composing',
  done: 'Done',
  failed: 'Failed',
  draft_ready: 'Draft Ready',
  regenerating: 'Regenerating',
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[status] || 'bg-gray-100 text-gray-600'}`}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}
