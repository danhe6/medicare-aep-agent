import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import Site from "./site/Site.jsx";
import "./index.css";

const path = window.location.pathname.replace(/\/+$/, "") || "/";
document.documentElement.classList.toggle("app", path.startsWith("/app"));
createRoot(document.getElementById("root")).render(path.startsWith("/app") ? <App /> : <Site path={path} />);
