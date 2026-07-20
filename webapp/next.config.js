/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // MongoDB is connected server-side only; nothing extra needed here.

  experimental: {
    // Disable the Client-Side Router Cache entirely.
    //
    // By default Next.js caches the RSC (React Server Component) payload
    // for every route the user has visited, for 30s (dynamic) or 5min
    // (static). When the user navigates back to a route — by clicking a
    // sidebar item, a row, a "back to ..." link, or via router.push()
    // after a mutation — Next.js reuses the cached payload instead of
    // re-running the server component.
    //
    // For this operations console that is wrong: lists must always
    // reflect the current DB state, never a stale snapshot. A user who
    // deletes an audio and then clicks back to /audios must NOT see the
    // deleted audio still in the list.
    //
    // Setting both staleTimes to 0 makes the cache always-stale, so
    // every navigation re-runs the server component and re-queries
    // MongoDB. This is the official Next.js way to opt out of the
    // Router Cache.
    //
    // See: https://nextjs.org/docs/app/api-reference/next-config-js/staleTimes
    staleTimes: {
      dynamic: 0,
      static: 0,
    },
  },
};
module.exports = nextConfig;
