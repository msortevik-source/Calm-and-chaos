import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;
export const API = `${BASE}/api`;

export const api = axios.create({ baseURL: API, timeout: 60000 });

export const getGreeting = () => api.get("/greeting").then(r => r.data);
export const sendChat = (text, mode = "send") => api.post("/chat", { text, mode }).then(r => r.data);
export const getChatRecent = () => api.get("/chat/recent").then(r => r.data);
export const getChatHistory = () => api.get("/chat/history").then(r => r.data);
export const clearChat = () => api.delete("/chat/history").then(r => r.data);

export const listBrainDumps = () => api.get("/braindump").then(r => r.data);
export const createBrainDump = (payload) => api.post("/braindump", payload).then(r => r.data);
export const deleteBrainDump = (id) => api.delete(`/braindump/${id}`).then(r => r.data);

export const getTemplate = () => api.get("/training/template").then(r => r.data);
export const listTraining = () => api.get("/training").then(r => r.data);
export const createTraining = (payload) => api.post("/training", payload).then(r => r.data);
export const deleteTraining = (id) => api.delete(`/training/${id}`).then(r => r.data);

export const listBudget = () => api.get("/budget").then(r => r.data);
export const createBudget = (payload) => api.post("/budget", payload).then(r => r.data);
export const deleteBudget = (id) => api.delete(`/budget/${id}`).then(r => r.data);

export const listMeals = () => api.get("/meal").then(r => r.data);
export const createMeal = (payload) => api.post("/meal", payload).then(r => r.data);
export const deleteMeal = (id) => api.delete(`/meal/${id}`).then(r => r.data);

export const getPatterns = () => api.get("/patterns").then(r => r.data);

export const calendarStatus = () => api.get("/calendar/status").then(r => r.data);
export const calendarToday = () => api.get("/calendar/today").then(r => r.data);
export const calendarLoginUrl = () => api.get("/oauth/calendar/login").then(r => r.data);
export const calendarUnlink = () => api.post("/calendar/unlink").then(r => r.data);

export const MOODS = [
  { id: "heavy", label: "heavy" },
  { id: "meh", label: "meh" },
  { id: "ok", label: "ok" },
  { id: "good", label: "good" },
  { id: "flying", label: "flying" },
];
