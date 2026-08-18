import { FormEvent, useState } from "react";
import { Building2, LogIn } from "lucide-react";

interface LoginViewProps {
  busy: string | null;
  error: string | null;
  onLogin: (username: string, password: string) => Promise<void>;
}

export function LoginView({ busy, error, onLogin }: LoginViewProps) {
  const [username, setUsername] = useState("teste");
  const [password, setPassword] = useState("teste");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onLogin(username.trim(), password);
  }

  return (
    <main className="login-screen">
      <form className="login-panel blueprint" onSubmit={submit}>
        <i className="corner tl" />
        <i className="corner tr" />
        <i className="corner bl" />
        <i className="corner br" />
        <div className="login-mark">
          <Building2 size={24} />
        </div>
        <div>
          <p className="kicker">Acesso</p>
          <h1>Obra Barata</h1>
        </div>
        <label className="field">
          <span>Usuario</span>
          <input
            className="input"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoFocus
          />
        </label>
        <label className="field">
          <span>Senha</span>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error ? <div className="alert error">{error}</div> : null}
        <button className="btn btn-primary full" type="submit" disabled={Boolean(busy)}>
          <LogIn size={16} />
          {busy ? busy : "Entrar"}
        </button>
      </form>
    </main>
  );
}
