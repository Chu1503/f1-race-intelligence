interface ServiceAuthEnvironment {
  [key: string]: string | undefined;
  SERVICE_API_KEY?: string;
  API_SERVICE_KEY?: string;
}

export function getServiceApiKey(environment: ServiceAuthEnvironment): string {
  return environment.SERVICE_API_KEY?.trim() || environment.API_SERVICE_KEY?.trim() || "";
}
