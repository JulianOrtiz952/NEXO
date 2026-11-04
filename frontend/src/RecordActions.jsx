// RNF-029/031: shared per-record actions, with text alternatives and touch targets.
const icons = {
  status: 'M12 3v9 M6.3 5.7a8 8 0 1 0 11.4 0',
  price: 'M3 3h7l11 11-7 7L3 10V3Z M7.5 7.5h.01',
  edit: 'm15 5 4 4 M4 20l4-1 12-12a2.8 2.8 0 0 0-4-4L4 15v5Z',
  description: 'M7 3h8l4 4v14H5V3h2Z M14 3v5h5 M8 12h8 M8 16h6',
  up: 'm6 12 6-6 6 6 M12 6v14',
  down: 'm6 12 6 6 6-6 M12 4v14',
  link: 'm10 13 4-4 M8 16l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0 M16 8l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0',
  access: 'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z M9 12l2 2 4-4',
  role: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z M4 21v-2a8 8 0 0 1 16 0v2',
}

export default function RecordActions({ label, actions }) {
  return <div className="record-actions" role="group" aria-label={label}>
    {actions.map(action => <button key={action.id} type="button" className="record-action" disabled={action.disabled}
      aria-label={action.label} aria-expanded={action.expanded} aria-controls={action.controls} onClick={action.onClick}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d={icons[action.icon]} /></svg>
      <span className="record-action-hint" aria-hidden="true">{action.hint}</span>
    </button>)}
  </div>
}
