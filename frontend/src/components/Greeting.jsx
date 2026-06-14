import { useEffect, useState } from "react";
import { getGreeting } from "../lib/api";

const dayName = () => new Date().toLocaleDateString("en-US", { weekday: "long" });
const dateLine = () => new Date().toLocaleDateString("en-US", { month: "long", day: "numeric" });
const hearthNotes = [
  "Quiet scan: nothing appears to be actively on fire.",
  "The records are awake. Rude, but useful.",
  "Rainy cabin protocol: small steps, warm light, fewer heroic plans.",
  "The house is holding the list so your head does not have to.",
  "Today looks manageable if nobody starts inventing side quests.",
  "Ledger appears stable.",
  "Three thoughts remain unsupervised.",
  "The trails have been quiet lately.",
  "The board is collecting ideas again.",
  "The house spirit approves of today's coffee.",
  "One project appears to have escaped containment.",
  "A small amount of order has been detected.",
  "No alarms from the ledger shelf.",
  "The notice board is pretending to be casual.",
  "Trail records are resting their boots.",
  "Current forecast: manageable, with scattered nonsense.",
];

function hearthNote() {
  const today = new Date();
  const dayNumber = Math.floor(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) / 86400000);
  return hearthNotes[dayNumber % hearthNotes.length];
}

export default function Greeting() {
  const [g, setG] = useState({ greeting: "", sub: "", time_of_day: "", status_line: "" });

  useEffect(() => {
    getGreeting().then(setG).catch(() => {});
  }, []);

  return (
    <div className="animate-fade-up" data-testid="greeting-area">
      <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-3">
        {g.status_line || "The hearth"} / {dayName()} / {dateLine()}
      </div>
      <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl text-moss-50 leading-[1.05]">
        {g.greeting || "\u00A0"}
      </h1>
      {g.sub && (
        <p className="mt-4 text-moss-200 text-base md:text-lg font-body italic max-w-xl">
          {g.sub}
        </p>
      )}
      <p className="mt-4 house-spirit-note rounded-md px-3 py-2 text-sm inline-block">
        {hearthNote()}
      </p>
    </div>
  );
}
