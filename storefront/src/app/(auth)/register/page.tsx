import type { Metadata } from "next";
import AuthForm from "../components/AuthForm";

export const metadata: Metadata = {
  title: "Create Account — Blue Panda Tech Store",
  description:
    "Join Blue Panda to track orders, save hardware to your wishlist, and enjoy seamless tech checkout.",
};

export default function RegisterPage() {
  return <AuthForm mode="register" />;
}
