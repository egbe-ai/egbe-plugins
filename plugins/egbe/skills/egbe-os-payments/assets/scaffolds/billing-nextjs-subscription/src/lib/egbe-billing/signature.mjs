import { createHmac, timingSafeEqual } from "node:crypto";

export function verifyPaymentSignature(rawBody, header, secret, nowSeconds = Math.floor(Date.now() / 1000)) {
  const parts = String(header || "").split(",").map((part) => part.trim());
  const timestamps = parts.filter((part) => part.startsWith("t="));
  const signatures = parts.filter((part) => part.startsWith("v1="));
  if (timestamps.length !== 1 || signatures.length !== 1) throw new Error("Malformed payment signature");
  const timestampText = timestamps[0].slice(2);
  const signature = signatures[0].slice(3);
  if (!/^\d{10,}$/.test(timestampText) || !/^[0-9a-f]{64}$/.test(signature)) {
    throw new Error("Malformed payment signature");
  }
  const timestamp = Number(timestampText);
  if (timestamp > nowSeconds + 60 || nowSeconds - timestamp > 300) {
    throw new Error("Stale payment signature");
  }
  const expected = createHmac("sha256", secret).update(`${timestamp}.${rawBody}`).digest("hex");
  if (!timingSafeEqual(Buffer.from(expected, "hex"), Buffer.from(signature, "hex"))) {
    throw new Error("Invalid payment signature");
  }
  return timestamp;
}
