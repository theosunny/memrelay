export function encryptBlob(keyB64: string, plaintext: Uint8Array): Promise<string>;
export function decryptBlob(keyB64: string, token: string): Promise<Uint8Array>;
