import { useState } from "react";
import Greeting from "../components/Greeting";
import CalendarSnapshot from "../components/CalendarSnapshot";
import ConversationSnapshot from "../components/ConversationSnapshot";
import ChatInput from "../components/ChatInput";
import { sendChat } from "../lib/api";
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
      toast("The goblin is quiet right now. Try again.", { description: e?.response?.data?.detail || "" });
      throw e;
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-6 md:px-12 lg:px-20 py-10 md:py-16 max-w-7xl mx-auto" data-testid="home-page">
      <Greeting />

      <div className="mt-12 md:mt-16 grid grid-cols-1 lg:grid-cols-12 gap-6 md:gap-8">
        {/* Chat input — primary, asymmetric large slot */}
        <div className="lg:col-span-7 lg:col-start-1">
          <div className="mb-3 text-xs uppercase tracking-[0.25em] text-moss-200/70">Drop thought here</div>
          <ChatInput onSubmit={submit} busy={busy} />

          {lastReply?.assistant_msg && (
            <div className="mt-6 rounded-3xl border border-amber/30 bg-amber-soft p-5 animate-fade-up" data-testid="latest-reply">
              <div className="text-[10px] uppercase tracking-[0.25em] text-amber/90 mb-2">the goblin</div>
              <p className="font-heading text-lg md:text-xl text-moss-50 leading-snug italic">
                {lastReply.assistant_msg.text}
              </p>
            </div>
          )}
        </div>

        {/* Side column — calendar + conv snapshot */}
        <div className="lg:col-span-5 lg:col-start-8 space-y-6">
          <CalendarSnapshot />
          <ConversationSnapshot refreshKey={refresh} />
        </div>
      </div>
    </div>
  );
}
