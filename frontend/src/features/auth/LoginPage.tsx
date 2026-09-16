import { useState, type ChangeEvent, type FormEvent } from 'react';
import { Feedback } from '../../ui';

interface Props {
  busy: boolean;
  error: string;
  notice: string;
  onConnect: (credential: string) => Promise<void>;
}

export function LoginPage({ busy, error, notice, onConnect }: Props) {
  const [credential, setCredential] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = credential.trim();
    if (!value || busy) return;
    await onConnect(value);
  }

  return (
    <main className="login-layout">
      <section className="login-story">
        <div className="brand"><span className="brandmark">R</span><span>RAGOps Studio</span></div>
        <div>
          <span className="eyebrow light">KNOWLEDGE OPERATIONS</span>
          <h1>Every answer.<br />A source you<br />can verify.</h1>
          <p>Search with context. Respect access boundaries.<br />Know when the evidence is not enough.</p>
          <div className="login-features">
            <span>01 &nbsp; Evidence-led workflows</span>
            <span>02 &nbsp; Tenant & department access</span>
            <span>03 &nbsp; Versioned source records</span>
          </div>
        </div>
        <small>Built for inspectable knowledge workflows.</small>
      </section>
      <section className="login-form">
        <div className="login-card">
          <span className="eyebrow">WORKSPACE ACCESS</span>
          <h2>Connect to your workspace</h2>
          <p>Enter a credential issued by your workspace administrator.</p>
          <Feedback error={error} notice={notice} />
          <form id="login-form" onSubmit={submit}>
            <label htmlFor="token">Access credential</label>
            <input
              type="password"
              id="token"
              autoComplete="off"
              required
              value={credential}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setCredential(event.target.value)}
              placeholder="Paste your workspace credential"
            />
            <button className="button primary wide" disabled={busy}>
              {busy ? 'Connecting…' : 'Connect workspace →'}
            </button>
          </form>
          <div className="login-help">
            <strong>First time running this installation?</strong>
            <p>Initialize workspace identities and the sample corpus:</p>
            <code>python scripts/bootstrap.py --with-sample-data</code>
            <p>Your generated credentials are stored locally in<br /><code>.secrets/access-credentials.txt</code>.</p>
          </div>
        </div>
      </section>
    </main>
  );
}
