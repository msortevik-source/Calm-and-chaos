import { useState } from "react";
import Greeting from "../components/Greeting";
import Goblin from "../components/Goblin";
import CalendarSnapshot from "../components/CalendarSnapshot";
import ConversationSnapshot from "../components/ConversationSnapshot";
import ChatInput from "../components/ChatInput";
import LetterCard from "../components/LetterCard";
import { sendChat } from "../lib/api";
import { renderInline } from "../lib/markdown";
import { toast } from "sonner";

export default function HomePage() {
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [lastReply, setLastReply] = useState(null);

  const submit = async (text, mode) => {
    setBusy(true);
    try {
      const res = await sendChat(text, mode);
      setLastReply(res);
      setRefresh(x => x + 1);
    } catch (e) {
      toast("Analysis is quiet right now. Try again.", { description: e?.response?.data?.detail || "" });
      throw e;
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-5 md:px-12 lg:px-20 py-7 md:py-16 max-w-7xl mx-auto" data-testid="home-page">
      <div className="flex items-end gap-6 md:gap-10 flex-wrap md:flex-nowrap">
        <div className="relative shrink-0 hidden sm:block" data-testid="goblin-area">
          <div className="goblin-glow" />
          <Goblin size={220} />
        </div>
        <div className="flex-1 min-w-0">
          <Greeting />
        </div>
      </div>

      <div className="mt-12 md:mt-16 grid grid-cols-1 lg:grid-cols-12 gap-6 md:gap-8">
        {/* Chat input — primary, asymmetric large slot */}
        <div className="lg:col-span-7 lg:col-start-1">
          <div className="mb-3 text-xs uppercase tracking-[0.25em] text-moss-200/70">Hearth note</div>
          <ChatInput onSubmit={submit} busy={busy} placeholder="Ask what changed, what needs sorting, or where the receipts are pointing." />

          {lastReply?.assistant_msg && (
            <div className="mt-6 rounded-3xl warm-card p-5 animate-fade-up" style={{ background: "linear-gradient(180deg, rgba(212,163,115,0.10) 0%, rgba(43,47,42,0.85) 100%)" }} data-testid="latest-reply">
              <div className="text-[10px] uppercase tracking-[0.25em] text-amber/90 mb-2">house spirit noticed</div>
              <p className="font-body text-base md:text-lg text-moss-50 leading-relaxed">
                {renderInline(lastReply.assistant_msg.text)}
              </p>
            </div>
          )}
        </div>

        {/* Side column — calendar + conv snapshot + letter + evening check-in */}
        <div className="lg:col-span-5 lg:col-start-8 space-y-6">
          <CalendarSnapshot />
          <LetterCard />
          <ConversationSnapshot refreshKey={refresh} />
        </div>
      </div>
    </div>
  );
}
