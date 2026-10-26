// Se ejecuta automáticamente SOLO la primera vez que MongoDB arranca
// con el volumen vacío. Crea un usuario de aplicación con permisos
// limitados a la base de datos del proyecto (principio de mínimo privilegio).

const dbName = process.env.MONGO_DATABASE || "proyecto_noaa";
const appUser = process.env.MONGO_APP_USERNAME;
const appPassword = process.env.MONGO_APP_PASSWORD;

if (!appUser || !appPassword) {
  throw new Error("Faltan MONGO_APP_USERNAME o MONGO_APP_PASSWORD.");
}

const target = db.getSiblingDB(dbName);

if (target.getUser(appUser)) {
  print(`El usuario ${appUser} ya existe; no se modifica.`);
} else {
  target.createUser({
    user: appUser,
    pwd: appPassword,
    roles: [{ role: "readWrite", db: dbName }],
  });
  print(`Usuario de aplicación ${appUser} creado sobre ${dbName}.`);
}
