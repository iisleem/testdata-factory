package dev.testdatafactory.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

final class LocalGenerator {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final List<String> FIRST_NAMES = List.of("Nora", "Maya", "Adam", "Omar", "Lina", "Sam");
    private static final List<String> LAST_NAMES = List.of("Stone", "Rivera", "Saleh", "Carter", "Haddad", "Kim");
    private static final List<String> COUNTRY_CODES = List.of("US", "CA", "GB", "AU", "DE", "FR", "JO");
    private static final List<String> CITIES = List.of("Springfield", "Riverton", "Fairview", "Georgetown", "Franklin");
    private static final List<String> STATES = List.of("CA", "NY", "TX", "WA", "IL", "FL");
    private static final List<String> COUNTRIES = List.of(
        "United States",
        "Canada",
        "United Kingdom",
        "Australia",
        "Germany",
        "France",
        "Jordan"
    );
    private static final List<String> CURRENCIES = List.of("USD", "EUR", "GBP", "CAD", "AUD", "JPY", "JOD");
    private static final DateTimeFormatter DATETIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss");

    private LocalGenerator() {
    }

    static List<Map<String, Object>> generate(JsonNode contract, String scenarioId, int count, String seed) {
        if (count < 1) {
            throw new IllegalArgumentException("count must be greater than 0");
        }

        JsonNode scenario = findScenario(contract, scenarioId);
        String baseSeed = seed != null ? seed : contract.path("generation").path("defaultSeed").asText();
        List<Map<String, Object>> records = new ArrayList<>();
        for (int index = 0; index < count; index += 1) {
            records.add(generateRecord(contract, scenario, scenarioId, baseSeed, index));
        }
        return records;
    }

    private static Map<String, Object> generateRecord(
        JsonNode contract,
        JsonNode scenario,
        String scenarioId,
        String seed,
        int index
    ) {
        Map<String, Object> record = new LinkedHashMap<>();
        JsonNode scenarioFields = scenario.path("fields");
        Iterator<Map.Entry<String, JsonNode>> fields = contract.path("fields").fields();

        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> entry = fields.next();
            String fieldName = entry.getKey();
            JsonNode field = entry.getValue();
            JsonNode override = scenarioFields.path(fieldName);

            if (override.has("value")) {
                record.put(fieldName, toPlainValue(override.path("value")));
                continue;
            }

            String strategy = override.has("strategy") ? override.path("strategy").asText() : defaultStrategy(field);
            if ("missing".equals(strategy) || "missing_required".equals(strategy)) {
                continue;
            }

            record.put(fieldName, runStrategy(field, strategy, seed, scenarioId, index, fieldName));
        }

        return record;
    }

    private static JsonNode findScenario(JsonNode contract, String scenarioId) {
        for (JsonNode scenario : contract.path("scenarios")) {
            if (scenarioId.equals(scenario.path("id").asText())) {
                return scenario;
            }
        }
        throw new IllegalArgumentException("Unknown scenario: " + scenarioId);
    }

    private static String defaultStrategy(JsonNode field) {
        return switch (field.path("businessType").asText()) {
            case "first_name" -> "valid_first_name";
            case "last_name" -> "valid_last_name";
            case "full_name" -> "valid_full_name";
            case "username" -> "valid_username";
            case "email" -> "valid_email";
            case "password" -> "valid_password";
            case "phone_number" -> "valid_phone";
            case "country_code" -> "valid_country_code";
            case "address_line" -> "valid_address_line";
            case "city" -> "valid_city";
            case "state" -> "valid_state";
            case "postal_code" -> "valid_postal_code";
            case "country" -> "valid_country";
            case "integer", "quantity" -> "valid_integer";
            case "decimal", "amount", "percentage" -> "valid_decimal";
            case "currency" -> "valid_currency";
            case "enum" -> "valid_enum";
            case "date", "date_of_birth" -> "valid_date";
            case "time" -> "valid_time";
            case "datetime" -> "valid_datetime";
            case "boolean" -> "valid_boolean";
            case "url" -> "valid_url";
            case "domain" -> "valid_domain";
            case "uuid" -> "valid_uuid";
            case "national_id" -> "valid_national_id";
            case "passport_number" -> "valid_passport_number";
            case "tax_id" -> "valid_tax_id";
            case "account_number" -> "valid_account_number";
            case "iban" -> "valid_iban";
            case "credit_card_number" -> "valid_credit_card_number";
            case "cvv" -> "valid_cvv";
            case "expiry_date" -> "valid_expiry_date";
            case "otp" -> "valid_otp";
            case "free_text" -> "valid_free_text";
            default -> throw new IllegalArgumentException(
                "No default strategy for business type: " + field.path("businessType").asText()
            );
        };
    }

    private static Object runStrategy(
        JsonNode field,
        String strategy,
        String seed,
        String scenarioId,
        int index,
        String fieldName
    ) {
        String scope = scenarioId + ":" + fieldName;
        return switch (strategy) {
            case "valid_first_name" -> choice(field, seed, scope, index, FIRST_NAMES);
            case "valid_last_name" -> choice(field, seed, scope, index, LAST_NAMES);
            case "valid_full_name" -> validFullName(field, seed, scope, index);
            case "valid_username" -> "user_" + randomInt(field, seed, scope, index, 1000, 9999);
            case "valid_email" -> "user" + index + "." + randomInt(field, seed, scope, index, 1000, 9999) + "@example.test";
            case "invalid_email_format" -> "not-an-email";
            case "valid_phone" -> validPhone(field, seed, scope, index);
            case "invalid_phone_format" -> "not-a-phone";
            case "valid_country_code" -> choice(field, seed, scope, index, COUNTRY_CODES);
            case "valid_address_line" -> validAddressLine(field, seed, scope, index);
            case "valid_city" -> choice(field, seed, scope, index, CITIES);
            case "valid_state" -> choice(field, seed, scope, index, STATES);
            case "valid_postal_code" -> String.valueOf(randomInt(field, seed, scope, index, 10000, 99999));
            case "valid_country" -> choice(field, seed, scope, index, COUNTRIES);
            case "invalid_alpha" -> "abc";
            case "valid_password" -> "Tdf!" + randomInt(field, seed, scope, index, 100000, 999999) + "Pass";
            case "weak_password" -> "password";
            case "valid_integer" -> validInteger(field, seed, scope, index);
            case "valid_decimal" -> validDecimal(field, seed, scope, index);
            case "valid_enum" -> validEnum(field, seed, scope, index);
            case "valid_date" -> validDate(field, seed, scope, index);
            case "valid_time" -> validTime(field, seed, scope, index);
            case "valid_datetime" -> validDatetime(field, seed, scope, index);
            case "valid_boolean" -> randomInt(field, seed, scope, index, 0, 1) == 1;
            case "valid_currency" -> choice(field, seed, scope, index, CURRENCIES);
            case "valid_url" -> validUrl(field, seed, scope, index);
            case "valid_domain" -> validDomain(field, seed, scope, index);
            case "valid_uuid" -> validUuid(field, seed, scope, index);
            case "valid_national_id" -> "NID-" + randomInt(field, seed, scope, index, 100000000, 999999999);
            case "valid_passport_number" -> validPassportNumber(field, seed, scope, index);
            case "valid_tax_id" -> "TAX-" + randomInt(field, seed, scope, index, 10000000, 99999999);
            case "valid_account_number" -> "000" + randomInt(field, seed, scope, index, 100000000, 999999999);
            case "valid_iban" -> validIban(field, seed, scope, index);
            case "valid_credit_card_number" -> validCreditCardNumber(field, seed, scope, index);
            case "valid_cvv" -> String.format("%03d", randomInt(field, seed, scope, index, 0, 999));
            case "valid_expiry_date" -> validExpiryDate(field, seed, scope, index);
            case "valid_otp" -> String.format("%06d", randomInt(field, seed, scope, index, 0, 999999));
            case "valid_free_text" -> "Generated test note " + (index + 1);
            default -> throw new IllegalArgumentException("Unknown strategy: " + strategy);
        };
    }

    private static String validFullName(JsonNode field, String seed, String scope, int index) {
        String first = choice(field, seed, scope + ":first", index, FIRST_NAMES);
        String last = choice(field, seed, scope + ":last", index, LAST_NAMES);
        return first + " " + last;
    }

    private static String validAddressLine(JsonNode field, String seed, String scope, int index) {
        DeterministicRandom rng = rng(field, seed, scope, index);
        List<String> streets = List.of("Market Street", "Cedar Avenue", "River Road", "Summit Lane", "Atlas Way");
        return rng.nextInt(100, 999) + " " + streets.get(rng.nextInt(0, streets.size() - 1));
    }

    private static String validPhone(JsonNode field, String seed, String scope, int index) {
        String country = field.path("constraints").path("country").asText("US");
        int suffix = randomInt(field, seed, scope, index, 1000, 9999);
        if ("US".equals(country)) {
            return "+155501" + suffix;
        }
        return "+100000" + suffix;
    }

    private static int validInteger(JsonNode field, String seed, String scope, int index) {
        JsonNode constraints = field.path("constraints");
        int minimum = constraints.path("minimum").asInt(1);
        int maximum = constraints.path("maximum").asInt(999);
        return randomInt(field, seed, scope, index, minimum, maximum);
    }

    private static double validDecimal(JsonNode field, String seed, String scope, int index) {
        JsonNode constraints = field.path("constraints");
        double minimum = constraints.path("minimum").asDouble(1);
        double maximum = constraints.path("maximum").asDouble(999);
        double value = minimum + rng(field, seed, scope, index).nextDouble() * (maximum - minimum);
        return Math.round(value * 100.0) / 100.0;
    }

    private static Object validEnum(JsonNode field, String seed, String scope, int index) {
        JsonNode values = field.path("constraints").path("values");
        if (!values.isArray() || values.isEmpty()) {
            throw new IllegalArgumentException("enum field requires constraints.values");
        }
        int selected = rng(field, seed, scope, index).nextInt(0, values.size() - 1);
        return toPlainValue(values.get(selected));
    }

    private static String validDate(JsonNode field, String seed, String scope, int index) {
        int days = randomInt(field, seed, scope, index, 0, 10_000);
        return LocalDate.of(1990, 1, 1).plusDays(days).toString();
    }

    private static String validTime(JsonNode field, String seed, String scope, int index) {
        DeterministicRandom rng = rng(field, seed, scope, index);
        return String.format("%02d:%02d:00", rng.nextInt(0, 23), rng.nextInt(0, 59));
    }

    private static String validDatetime(JsonNode field, String seed, String scope, int index) {
        DeterministicRandom rng = rng(field, seed, scope, index);
        LocalDateTime value = LocalDateTime.of(2024, 1, 1, 9, 0, 0)
            .plusDays(rng.nextInt(0, 365))
            .plusMinutes(rng.nextInt(0, 8 * 60));
        return value.format(DATETIME_FORMATTER) + "Z";
    }

    private static String validUrl(JsonNode field, String seed, String scope, int index) {
        return "https://app-" + randomInt(field, seed, scope, index, 100, 999) + ".example.test/resource-" + (index + 1);
    }

    private static String validDomain(JsonNode field, String seed, String scope, int index) {
        return "service-" + randomInt(field, seed, scope, index, 100, 999) + ".example.test";
    }

    private static String validUuid(JsonNode field, String seed, String scope, int index) {
        String value = seed + ":" + scope + ":" + field.path("businessType").asText() + ":" + index;
        return UUID.nameUUIDFromBytes(value.getBytes(StandardCharsets.UTF_8)).toString();
    }

    private static String validPassportNumber(JsonNode field, String seed, String scope, int index) {
        DeterministicRandom rng = rng(field, seed, scope, index);
        List<String> prefixes = List.of("P", "T", "X");
        return prefixes.get(rng.nextInt(0, prefixes.size() - 1)) + rng.nextInt(10000000, 99999999);
    }

    private static String validIban(JsonNode field, String seed, String scope, int index) {
        String bban = String.format("TEST123456%08d", randomInt(field, seed, scope, index, 0, 99999999));
        return "GB" + ibanCheckDigits("GB", bban) + bban;
    }

    private static String validCreditCardNumber(JsonNode field, String seed, String scope, int index) {
        String body = String.format("411111%09d", randomInt(field, seed, scope, index, 0, 999999999));
        return body + luhnCheckDigit(body);
    }

    private static String validExpiryDate(JsonNode field, String seed, String scope, int index) {
        DeterministicRandom rng = rng(field, seed, scope, index);
        int month = rng.nextInt(1, 12);
        int year = 30 + rng.nextInt(0, 9);
        return String.format("%02d/%02d", month, year);
    }

    private static int randomInt(JsonNode field, String seed, String scope, int index, int minimum, int maximum) {
        return rng(field, seed, scope, index).nextInt(minimum, maximum);
    }

    private static <T> T choice(JsonNode field, String seed, String scope, int index, List<T> values) {
        int selected = rng(field, seed, scope, index).nextInt(0, values.size() - 1);
        return values.get(selected);
    }

    private static DeterministicRandom rng(JsonNode field, String seed, String scope, int index) {
        return new DeterministicRandom(stableSeed(seed, scope, field.path("businessType").asText(), index));
    }

    private static Object toPlainValue(JsonNode value) {
        return OBJECT_MAPPER.convertValue(value, Object.class);
    }

    private static String ibanCheckDigits(String countryCode, String bban) {
        int remainder = ibanMod97(bban + countryCode + "00");
        return String.format("%02d", 98 - remainder);
    }

    private static int ibanMod97(String value) {
        int remainder = 0;
        for (int index = 0; index < value.length(); index += 1) {
            char character = Character.toUpperCase(value.charAt(index));
            String digits;
            if (Character.isDigit(character)) {
                digits = String.valueOf(character);
            } else if (Character.isLetter(character)) {
                digits = String.valueOf(character - 'A' + 10);
            } else {
                continue;
            }
            for (int digitIndex = 0; digitIndex < digits.length(); digitIndex += 1) {
                remainder = (remainder * 10 + Character.digit(digits.charAt(digitIndex), 10)) % 97;
            }
        }
        return remainder;
    }

    private static String luhnCheckDigit(String number) {
        int total = 0;
        for (int index = number.length() - 1, position = 0; index >= 0; index -= 1, position += 1) {
            int digit = Character.digit(number.charAt(index), 10);
            if (position % 2 == 0) {
                digit *= 2;
                if (digit > 9) {
                    digit -= 9;
                }
            }
            total += digit;
        }
        return String.valueOf((10 - total % 10) % 10);
    }

    private static long stableSeed(Object... parts) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (Object part : parts) {
                digest.update(String.valueOf(part).getBytes(StandardCharsets.UTF_8));
                digest.update((byte) 0);
            }
            byte[] hash = digest.digest();
            long value = 0;
            for (int index = 0; index < Long.BYTES; index += 1) {
                value = (value << 8) | (hash[index] & 0xffL);
            }
            return value;
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException("SHA-256 is not available", exc);
        }
    }

    private static final class DeterministicRandom {
        private static final long INCREMENT = 0x9E3779B97F4A7C15L;
        private static final long MIX_A = 0xBF58476D1CE4E5B9L;
        private static final long MIX_B = 0x94D049BB133111EBL;

        private long state;

        DeterministicRandom(long seed) {
            this.state = seed;
        }

        int nextInt(int minimum, int maximum) {
            int bound = maximum - minimum + 1;
            return minimum + (int) Long.remainderUnsigned(nextLong(), bound);
        }

        double nextDouble() {
            return (nextLong() >>> 11) * 0x1.0p-53;
        }

        private long nextLong() {
            state += INCREMENT;
            long value = state;
            value = (value ^ (value >>> 30)) * MIX_A;
            value = (value ^ (value >>> 27)) * MIX_B;
            return value ^ (value >>> 31);
        }
    }
}
