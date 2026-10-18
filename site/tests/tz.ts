// Throw times are shown in the machine's local zone, so pin one for repeatable tests.
export default function setup() {
  process.env.TZ = "America/New_York";
}
