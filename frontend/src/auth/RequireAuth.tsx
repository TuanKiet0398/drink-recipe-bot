import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function RequireAuth({
  children,
  adminOnly = false,
}: {
  children: JSX.Element;
  adminOnly?: boolean;
}) {
  const { isAuthenticated, isAdmin } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (adminOnly && !isAdmin) {
    return <Navigate to="/panel/chat" replace />;
  }
  return children;
}
