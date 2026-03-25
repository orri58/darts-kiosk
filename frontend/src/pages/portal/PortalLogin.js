import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useCentralAuth } from "../../context/CentralAuthContext";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";

export default function PortalLogin() {
  const { login, isAuthenticated } = useCentralAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/portal" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: "#0a0a0f" }}
      data-testid="portal-login-page"
    >
      <Card className="w-full max-w-sm border-zinc-800 bg-zinc-900/80">
        <CardHeader className="text-center pb-2">
          <CardTitle className="text-xl text-zinc-100">Central Portal</CardTitle>
          <p className="text-sm text-zinc-500 mt-1">Layer A — Read-Only Visibility</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Input
                data-testid="portal-login-username"
                placeholder="Benutzername"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-zinc-100"
                autoFocus
              />
            </div>
            <div>
              <Input
                data-testid="portal-login-password"
                type="password"
                placeholder="Passwort"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-zinc-100"
              />
            </div>
            {error && (
              <p data-testid="portal-login-error" className="text-red-400 text-sm">
                {error}
              </p>
            )}
            <Button
              data-testid="portal-login-submit"
              type="submit"
              className="w-full"
              disabled={loading || !username || !password}
            >
              {loading ? "..." : "Anmelden"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
