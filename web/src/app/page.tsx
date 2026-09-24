import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export default function HomePage() {
  // Land each role where it belongs (the edge middleware enforces the same rule
  // for direct hits on admin-only paths).
  const role = cookies().get("role")?.value;
  redirect(role === "ADMIN" ? "/dashboard" : "/maps");
}
