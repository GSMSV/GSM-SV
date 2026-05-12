export const config = {
  port: parseInt(process.env.PORT || "3001"),
  databaseUrl: process.env.DATABASE_URL || "",
  maxFunctionsPerUser: parseInt(process.env.MAX_FUNCTIONS_PER_USER || "5"),
  nodeEnv: process.env.NODE_ENV || "development",
};
