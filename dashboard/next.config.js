/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config, { isServer }) => {
    if (isServer) {
      // Keep better-sqlite3 as an external — it's a native module
      config.externals = [...(config.externals || []), 'better-sqlite3'];
    }
    return config;
  },
};

module.exports = nextConfig;
