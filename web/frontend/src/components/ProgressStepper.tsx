const STAGES = [
  { key: 'draft', label: 'Draft' },
  { key: 'scripting', label: 'Script' },
  { key: 'storyboarding', label: 'Storyboard' },
  { key: 'generating', label: 'Generate' },
  { key: 'composing', label: 'Compose' },
  { key: 'done', label: 'Done' },
];

const STAGE_ORDER: Record<string, number> = {
  draft: 0, scripting: 1, storyboarding: 2, generating: 3, composing: 4, done: 5, failed: -1,
};

export default function ProgressStepper({ currentStatus }: { currentStatus: string }) {
  const current = STAGE_ORDER[currentStatus] ?? -1;

  return (
    <div className="flex items-center gap-1 py-4">
      {STAGES.map((s, i) => {
        const isActive = current === i;
        const isDone = current > i;
        const isFailed = currentStatus === 'failed' && i === STAGES.length - 1;
        return (
          <div key={s.key} className="flex items-center flex-1 last:flex-none">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold
              ${isActive ? 'bg-indigo-600 text-white ring-2 ring-indigo-300' :
                isDone ? 'bg-green-500 text-white' :
                isFailed ? 'bg-red-500 text-white' :
                'bg-gray-200 text-gray-500'}`}>
              {isDone ? '✓' : isFailed ? '✗' : i + 1}
            </div>
            <span className={`ml-1 text-xs ${isActive ? 'text-indigo-700 font-medium' : 'text-gray-400'}`}>
              {s.label}
            </span>
            {i < STAGES.length - 1 && <div className={`flex-1 h-0.5 mx-2 ${isDone ? 'bg-green-500' : 'bg-gray-200'}`} />}
          </div>
        );
      })}
    </div>
  );
}
