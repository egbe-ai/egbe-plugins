export function verifyPaymentSignature(
  rawBody: string,
  header: string | null,
  secret: string,
  nowSeconds?: number,
): number;
