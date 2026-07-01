/** Password policy: length ≥ 8, at least one uppercase, digit, and symbol. */

export const PASSWORD_RULES = [
  { id: "length", label: "Minimal 8 karakter", test: (p) => (p || "").length >= 8 },
  { id: "upper", label: "Mengandung huruf besar (A-Z)", test: (p) => /[A-Z]/.test(p || "") },
  { id: "digit", label: "Mengandung angka (0-9)", test: (p) => /[0-9]/.test(p || "") },
  { id: "symbol", label: "Mengandung simbol (!@#$%…)", test: (p) => /[^A-Za-z0-9]/.test(p || "") },
];

export function evaluatePassword(pwd) {
  const results = PASSWORD_RULES.map((r) => ({ ...r, ok: r.test(pwd) }));
  const passed = results.filter((r) => r.ok).length;
  const valid = passed === results.length;
  const strength = passed / results.length; // 0..1
  return { results, valid, strength };
}
