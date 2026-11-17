import type { Metadata } from "next";
import AuthForm from "../components/AuthForm";

export const metadata: Metadata = {
  title: "Sign In — Blue Panda Tech Store",
  description:
    "Sign in to your Blue Panda account to manage orders, track delivery, and browse premium tech gear.",
};

export default function LoginPage() {
  return <AuthForm mode="login" />;
}
