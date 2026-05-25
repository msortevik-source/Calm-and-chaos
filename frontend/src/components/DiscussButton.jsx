import { useNavigate } from "react-router-dom";
import { MessageCircle } from "lucide-react";

/**
 * Opens the analysis view with an entry-shaped seed string.
 * Takes an entry-shaped seed string, navigates to /conversation, prefills the input.
 */
export default function DiscussButton({ seed, testid }) {
  const navigate = useNavigate();
  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        navigate("/conversation", { state: { seed } });
      }}
      data-testid={testid || "discuss-button"}
      title="analyze this"
      className="opacity-30 hover:opacity-100 text-moss-200 hover:text-amber transition-opacity"
    >
      <MessageCircle size={15} />
    </button>
  );
}
