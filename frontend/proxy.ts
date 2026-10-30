import { NextRequest, NextResponse } from "next/server";

const protectedPages: Record<string, { role: string; message: string }> = {
  "/cartpage.html": { role: "customer", message: "Customer account required." },
  "/checkout.html": { role: "customer", message: "Customer account required." },
  "/orderpage.html": { role: "customer", message: "Customer account required." },
  "/resturenthomepage.html": { role: "restaurant", message: "Restaurant account required." },
  "/resturentorderpage.html": { role: "restaurant", message: "Restaurant account required." },
  "/resturentprofilepage.html": { role: "restaurant", message: "Restaurant account required." },
  "/resturentsettingpage.html": { role: "restaurant", message: "Restaurant account required." },
  "/resturentdeliverypage.html": { role: "delivery_partner", message: "Delivery partner account required." },
};

export async function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // Preserve Django's 404 behavior for unknown category/restaurant routes
  // before serving the static HTML shell.
  const routeParts = pathname.split("/").filter(Boolean);
  const isCategoryPath = routeParts[0] === "category";
  const isRestaurantPath = routeParts[0] === "restaurant";
  if ((isCategoryPath || isRestaurantPath) && routeParts.length !== 2) {
    return NextResponse.json({ message: "Page not found." }, { status: 404 });
  }
  const isCategoryRoute = isCategoryPath;
  const isRestaurantRoute = isRestaurantPath;
  if (isCategoryRoute || isRestaurantRoute) {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL;
    if (!backendUrl) {
      return NextResponse.json({ message: "NEXT_PUBLIC_API_URL is not configured." }, { status: 503 });
    }
    const apiPath = isCategoryRoute
      ? `/api/customer/categories/${encodeURIComponent(routeParts[1] || "")}`
      : `/api/customer/restaurants/${encodeURIComponent(routeParts[1])}`;
    try {
      const response = await fetch(new URL(apiPath, backendUrl), { method: "GET", cache: "no-store" });
      if (response.status === 404) {
        return NextResponse.json({ message: "Page not found." }, { status: 404 });
      }
      if (!response.ok) {
        return NextResponse.json({ message: "Could not verify this page with the backend." }, { status: 503 });
      }
    } catch {
      return NextResponse.json({ message: "Could not reach the backend." }, { status: 503 });
    }
  }

  const required = protectedPages[pathname];
  if (!required) return NextResponse.next();

  const backendUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!backendUrl) {
    return NextResponse.json({ message: "NEXT_PUBLIC_API_URL is not configured." }, { status: 503 });
  }

  const cookie = request.headers.get("cookie");
  if (!cookie) {
    return NextResponse.redirect(new URL("/login.html", request.url), 302);
  }

  let account: { role?: string };
  try {
    const response = await fetch(new URL("/api/auth/me", backendUrl), {
      headers: { cookie },
    });
    if (response.status === 401) {
      return NextResponse.redirect(new URL("/login.html", request.url), 302);
    }
    if (!response.ok) {
      return NextResponse.json({ message: required.message }, { status: 403 });
    }
    account = await response.json();
  } catch {
    return NextResponse.json(
      { message: "Could not verify the account with the backend." },
      { status: 503 },
    );
  }

  if (account.role !== required.role) {
    return NextResponse.json({ message: required.message }, { status: 403 });
  }

  if (pathname === "/resturentorderpage.html") {
    return NextResponse.redirect(
      new URL("/resturenthomepage.html#restaurant-orders", request.url),
      302,
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/category/:path*",
    "/restaurant/:path*",
    "/cartpage.html",
    "/checkout.html",
    "/orderpage.html",
    "/resturenthomepage.html",
    "/resturentorderpage.html",
    "/resturentprofilepage.html",
    "/resturentsettingpage.html",
    "/resturentdeliverypage.html",
  ],
};
