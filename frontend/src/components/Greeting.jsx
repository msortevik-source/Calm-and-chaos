import { useEffect, useState } from "react";
import { getGreeting } from "../lib/api";

const dayName = () => new Date().toLocaleDateString("en-US", { weekday: "long" });
const dateLine = () => new Date().toLocaleDateString("en-US", { month: "long", day: "numeric" });

export default function Greeting() {
  const [g, setG] = useState({ greeting: "", sub: "", time_of_day: "" });

  useEffect(() => {
    getGreeting().then(setG).catch(() => {});
  }, []);

  return (
    <div className="animate-fade-up" data-testid="greeting-area">
      <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-3">
        {dayName()} · {dateLine()}
      </div>
      <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl text-moss-50 leading-[1.05]">
        {g.greeting || "\u00A0"}
      </h1>
      {g.sub && (
        <p className="mt-4 text-moss-200 text-base md:text-lg font-body italic max-w-xl">
          {g.sub}
        </p>
      )}
    </div>
  );
}
