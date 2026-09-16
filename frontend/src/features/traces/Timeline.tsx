import type { Trace } from '../../types';
import { label } from '../../ui';

export function Timeline({ trace }: { trace: Trace }) {
  return (
    <div className="panel timeline">
      <div className="panel-heading">
        <h3>Execution path</h3>
        <code>{trace.trace_id.slice(0, 15)}…</code>
      </div>
      {trace.events.map((event, index) => (
        <div className="timeline-step" key={`${event.node}-${index}`}>
          <span>{String(index + 1).padStart(2, '0')}</span>
          <div>
            <strong>{label(event.node)}</strong>
            <p>{event.message}</p>
          </div>
          <span className="step-dot" />
        </div>
      ))}
    </div>
  );
}
