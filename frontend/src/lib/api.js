import axios from "axios";

const PROD_BACKEND = "https://calm-and-chaos-api.onrender.com";
const LOCAL_BACKEND = "http://127.0.0.1:8001";
const envBackend = process.env.REACT_APP_BACKEND_URL;
const isLocalBrowser = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const envLooksLocal = envBackend && /localhost|127\.0\.0\.1/.test(envBackend);
const BASE = ((envLooksLocal && !isLocalBrowser) ? PROD_BACKEND : (envBackend || (isLocalBrowser ? LOCAL_BACKEND : PROD_BACKEND))).replace(/\/$/, "");
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
export const stravaStatus = () => api.get("/strava/status").then(r => r.data);
export const stravaLoginUrl = () => api.get("/oauth/strava/login").then(r => r.data);
export const stravaImport = (payload = {}) => api.get(`/strava/import/recent?limit=${payload.limit || 10}`).then(r => r.data);
export const stravaUnlink = () => api.post("/strava/unlink").then(r => r.data);

export const listBudget = () => api.get("/budget").then(r => r.data);
export const createBudget = (payload) => api.post("/budget", payload).then(r => r.data);
export const deleteBudget = (id) => api.delete(`/budget/${id}`).then(r => r.data);
export const getBudgetV1 = (month) => api.get(`/budget/v1${month ? `?month=${month}` : ""}`).then(r => r.data);
export const saveBudgetSetup = (payload) => api.put("/budget/v1/setup", payload).then(r => r.data);
export const createSpending = (payload) => api.post("/budget/v1/spending", payload).then(r => r.data);
export const markSpendingCheckin = (payload) => api.post("/budget/v1/checkin", payload).then(r => r.data);
export const deleteSpending = (id) => api.delete(`/budget/v1/spending/${id}`).then(r => r.data);

export const listMeals = () => api.get("/meal").then(r => r.data);
export const createMeal = (payload) => api.post("/meal", payload).then(r => r.data);
export const deleteMeal = (id) => api.delete(`/meal/${id}`).then(r => r.data);
export const getFoodV1 = (weekStart) => api.get(`/food/v1${weekStart ? `?week_start=${weekStart}` : ""}`).then(r => r.data);
export const saveFoodV1 = (payload) => api.put("/food/v1", payload).then(r => r.data);

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
