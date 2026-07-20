"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

/**
 * useNavigateWithRefresh — navigate to a route while forcing the
 * destination to re-fetch its server-side data.
 *
 * Next.js App Router caches Server Component output in the Client-
 * Side Router Cache. When a mutation happens (e.g. deleting an audio)
 * and we then router.push('/audios'), the user often sees the STALE
 * list (the deleted audio still appears) because the cached RSC
 * payload is reused.
 *
 * Solution: call router.refresh() — which invalidates the entire
 * router cache, not just the current route — and then push. The
 * push will see no fresh cache entry for the destination and refetch.
 *
 * If for some reason refresh+push still serves stale data, fall back
 * to a full-page navigation via window.location. This is heavier
 * (full reload) but guaranteed fresh.
 */

export function useNavigateWithRefresh() {
  const router = useRouter();

  const navigate = useCallback(
    (href: string) => {
      // Invalidate the router cache.
      router.refresh();
      // Push to the destination — since the cache was just invalidated,
      // Next.js refetches the RSC payload for href.
      router.push(href);
    },
    [router],
  );

  return navigate;
}
