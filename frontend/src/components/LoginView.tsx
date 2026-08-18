import { FormEvent, useState } from "react";
import { Building2, LogIn } from "lucide-react";

interface LoginViewProps {
  onLogin: (name: string) => void;
}

export function LoginView({ onLogin }: LoginViewProps) {
  const [name, setName] = useState("Usuário Obra Barata");

  function submit(event: FormEvent) {
    event.preventDefault();
    onLogin(name.trim() || "Usuário Obra Barata");
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
          <span>Nome</span>
          <input
            className="input"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoFocus
          />
        </label>
        <button className="btn btn-primary full" type="submit">
          <LogIn size={16} />
          Entrar
        </button>
      </form>
    </main>
  );
}
