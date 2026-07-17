package dev.testdatafactory.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class LocalGenerator {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final List<String> FIRST_NAMES = List.of("Nora", "Maya", "Adam", "Omar", "Lina", "Sam");
    private static final List<String> LAST_NAMES = List.of("Stone", "Rivera", "Saleh", "Carter", "Haddad", "Kim");

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
            case "integer", "quantity" -> "valid_integer";
            case "decimal", "amount", "percentage" -> "valid_decimal";
            case "enum" -> "valid_enum";
            case "date", "date_of_birth" -> "valid_date";
            case "boolean" -> "valid_boolean";
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
            case "invalid_alpha" -> "abc";
            case "valid_password" -> "Tdf!" + randomInt(field, seed, scope, index, 100000, 999999) + "Pass";
            case "valid_integer" -> validInteger(field, seed, scope, index);
            case "valid_decimal" -> validDecimal(field, seed, scope, index);
            case "valid_enum" -> validEnum(field, seed, scope, index);
            case "valid_date" -> validDate(field, seed, scope, index);
            case "valid_boolean" -> randomInt(field, seed, scope, index, 0, 1) == 1;
            case "valid_free_text" -> "Generated test note " + (index + 1);
            default -> throw new IllegalArgumentException("Unknown strategy: " + strategy);
        };
    }

    private static String validFullName(JsonNode field, String seed, String scope, int index) {
        String first = choice(field, seed, scope + ":first", index, FIRST_NAMES);
        String last = choice(field, seed, scope + ":last", index, LAST_NAMES);
        return first + " " + last;
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
