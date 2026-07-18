package dev.testdatafactory.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TestDataFactoryClientTest {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final Path CONTRACT = Path.of("..", "examples", "contracts", "register.tdf.json");
    private static final Path SCHEMA = Path.of("..", "specs", "contract-schema", "tdf-contract.schema.json");

    @Test
    void loadsContractFixture() {
        ContractDocument contract = TestDataFactory.local().seed("java-sdk").contract(CONTRACT);

        assertEquals("register", contract.id());
        assertEquals("java-sdk", TestDataFactory.local().seed("java-sdk").defaultSeed());
    }

    @Test
    void createsScenarioRequest() {
        ContractDocument contract = TestDataFactory.local().contract(CONTRACT);
        ScenarioRequest scenario = contract.scenario("valid_signup");

        assertEquals("valid_signup", scenario.scenarioId());
        assertEquals("register", scenario.contract().id());
    }

    @Test
    void releaseSmokeGeneratesDeterministicRecords() {
        TestDataFactoryClient client = TestDataFactory.local().seed("release-java-sdk");

        List<Map<String, Object>> first = client.contract(CONTRACT).scenario("valid_signup").count(2);
        List<Map<String, Object>> second = client.contract(CONTRACT).scenario("valid_signup").count(2);
        Map<String, Object> invalidEmailUser = client.contract(CONTRACT).scenario("invalid_email_format").one();

        assertEquals(first, second);
        assertEquals(2, first.size());
        assertTrue(first.get(0).get("email").toString().endsWith("@example.test"));
        assertEquals("not-an-email", invalidEmailUser.get("email"));
    }

    @Test
    void generatesScenarioRecords() {
        List<Map<String, Object>> users = TestDataFactory.local()
            .seed("java-sdk")
            .contract(CONTRACT)
            .scenario("valid_signup")
            .count(2);

        assertEquals(2, users.size());
        Map<String, Object> first = users.get(0);
        assertEquals(
            List.of("firstName", "email", "phone", "password", "age", "plan", "birthDate", "newsletter"),
            List.copyOf(first.keySet())
        );
        assertTrue(first.get("email").toString().endsWith("@example.test"));
        assertTrue(first.get("phone").toString().startsWith("+155501"));
        assertTrue((Integer) first.get("age") >= 18);
        assertTrue((Integer) first.get("age") <= 99);
        assertTrue(List.of("basic", "pro", "enterprise").contains(first.get("plan")));
        assertTrue(first.get("newsletter") instanceof Boolean);
    }

    @Test
    void generationIsRepeatableForSameSeed() {
        List<Map<String, Object>> first = TestDataFactory.local()
            .seed("java-sdk")
            .contract(CONTRACT)
            .scenario("valid_signup")
            .count(2);
        List<Map<String, Object>> second = TestDataFactory.local()
            .seed("java-sdk")
            .contract(CONTRACT)
            .scenario("valid_signup")
            .count(2);
        List<Map<String, Object>> differentSeed = TestDataFactory.local()
            .seed("java-sdk-other")
            .contract(CONTRACT)
            .scenario("valid_signup")
            .count(2);

        assertEquals(first, second);
        assertNotEquals(first, differentSeed);
    }

    @Test
    void appliesNegativeScenarioStrategies() {
        Map<String, Object> user = TestDataFactory.local()
            .seed("java-sdk")
            .contract(CONTRACT)
            .scenario("invalid_email_format")
            .one();

        assertEquals("not-an-email", user.get("email"));
        assertTrue(user.get("password").toString().startsWith("Tdf!"));
    }

    @Test
    void appliesGeneratedImportNegativeScenarioStrategies() {
        ContractDocument contract = new ContractDocument(generatedImportNegativeContract(), "java-sdk");

        Map<String, Object> invalidPhoneUser = contract.scenario("invalid_phone_format").one();
        Map<String, Object> weakPasswordUser = contract.scenario("weak_password").one();

        assertEquals("not-a-phone", invalidPhoneUser.get("phone"));
        assertTrue(invalidPhoneUser.get("password").toString().startsWith("Tdf!"));
        assertEquals("password", weakPasswordUser.get("password"));
        assertTrue(weakPasswordUser.get("phone").toString().startsWith("+155501"));
    }

    @Test
    void appliesSecurityRobustnessBoundaryAndDuplicateStrategies() {
        ContractDocument contract = new ContractDocument(advancedGenerationContract(), "java-sdk-advanced");

        assertEquals("<script>alert('tdf')</script>", contract.scenario("xss_payloads").one().get("notes"));
        assertEquals("admin' OR '1'='1", contract.scenario("sql_injection_payloads").one().get("notes"));

        Map<String, Object> nullRecord = contract.scenario("null_required_fields").one();
        assertTrue(nullRecord.containsKey("email"));
        assertNull(nullRecord.get("email"));

        assertEquals("", contract.scenario("empty_string_fields").one().get("notes"));
        assertEquals("", contract.scenario("empty_dependent_date_field").one().get("endDate"));
        assertEquals("   ", contract.scenario("whitespace_only_fields").one().get("notes"));
        assertEquals(2, contract.scenario("below_min_length_fields").one().get("notes").toString().length());
        assertEquals(11, contract.scenario("over_max_length_fields").one().get("notes").toString().length());
        assertEquals(false, contract.scenario("boolean_false_boundaries").one().get("marketingOptIn"));
        assertEquals(true, contract.scenario("boolean_true_boundaries").one().get("marketingOptIn"));

        List<Map<String, Object>> duplicateRecords = contract.scenario("duplicate_unique_fields").count(2);
        assertEquals("duplicate@example.test", duplicateRecords.get(0).get("email"));
        assertEquals(duplicateRecords.get(0).get("email"), duplicateRecords.get(1).get("email"));
    }

    @Test
    void appliesCrossFieldDependenciesForValidAndInvalidRecords() {
        ContractDocument contract = new ContractDocument(advancedGenerationContract(), "java-sdk-advanced");

        Map<String, Object> happyRecord = contract.scenario("valid_advanced").one();
        Map<String, Object> explicitValidRecord = contract.scenario("explicit_valid_relationships").one();
        Map<String, Object> rangeEndStrategyRecord = contract.scenario("range_end_after_start_relationship").one();
        Map<String, Object> normalOverrideRecord = contract.scenario("normal_strategy_confirmation_matches").one();
        Map<String, Object> mismatchRecord = contract.scenario("mismatched_confirmation_fields").one();
        Map<String, Object> invalidDateRecord = contract.scenario("invalid_date_ranges").one();
        Map<String, Object> invalidNumericRecord = contract.scenario("invalid_numeric_ranges").one();

        assertEquals(happyRecord.get("password"), happyRecord.get("confirmPassword"));
        assertTrue(LocalDate.parse(happyRecord.get("endDate").toString())
            .isAfter(LocalDate.parse(happyRecord.get("startDate").toString())));
        assertTrue((Integer) happyRecord.get("maxGuests") >= (Integer) happyRecord.get("minGuests"));

        assertEquals(explicitValidRecord.get("password"), explicitValidRecord.get("confirmPassword"));
        assertTrue(LocalDate.parse(explicitValidRecord.get("endDate").toString())
            .isAfter(LocalDate.parse(explicitValidRecord.get("startDate").toString())));
        assertTrue((Integer) explicitValidRecord.get("maxGuests") >= (Integer) explicitValidRecord.get("minGuests"));

        assertTrue(LocalDate.parse(rangeEndStrategyRecord.get("endDate").toString())
            .isAfter(LocalDate.parse(rangeEndStrategyRecord.get("startDate").toString())));
        assertEquals(normalOverrideRecord.get("password"), normalOverrideRecord.get("confirmPassword"));
        assertNotEquals("password", normalOverrideRecord.get("confirmPassword"));
        assertNotEquals(mismatchRecord.get("password"), mismatchRecord.get("confirmPassword"));
        assertTrue(LocalDate.parse(invalidDateRecord.get("endDate").toString())
            .isBefore(LocalDate.parse(invalidDateRecord.get("startDate").toString())));
        assertTrue((Integer) invalidNumericRecord.get("maxGuests") < (Integer) invalidNumericRecord.get("minGuests"));
    }

    @Test
    void unknownScenarioFailsClearly() {
        ScenarioRequest scenario = TestDataFactory.local().contract(CONTRACT).scenario("missing_scenario");

        IllegalArgumentException error = assertThrows(IllegalArgumentException.class, scenario::one);

        assertTrue(error.getMessage().contains("Unknown scenario: missing_scenario"));
    }

    @Test
    void defaultGenerationCoversAllSchemaBusinessTypes() throws IOException {
        List<String> businessTypes = schemaBusinessTypes();
        ContractDocument contract = new ContractDocument(businessTypeContract(businessTypes), "java-sdk");

        List<Map<String, Object>> first = contract.scenario("default_business_types").count(2);
        List<Map<String, Object>> second = contract.scenario("default_business_types").count(2);

        assertEquals(first, second);
        assertEquals(Set.copyOf(businessTypes), Set.copyOf(first.get(0).keySet()));
        assertBusinessTypeRecord(first.get(0));
    }

    private static List<String> schemaBusinessTypes() throws IOException {
        JsonNode values = OBJECT_MAPPER
            .readTree(SCHEMA.toFile())
            .path("$defs")
            .path("field")
            .path("properties")
            .path("businessType")
            .path("enum");
        List<String> businessTypes = new java.util.ArrayList<>();
        for (JsonNode value : values) {
            businessTypes.add(value.asText());
        }
        return businessTypes;
    }

    private static JsonNode businessTypeContract(List<String> businessTypes) {
        Map<String, Object> fields = new LinkedHashMap<>();
        for (String businessType : businessTypes) {
            fields.put(businessType, businessTypeField(businessType));
        }

        return OBJECT_MAPPER.valueToTree(
            Map.of(
                "schemaVersion", "1.0",
                "id", "business-type-defaults",
                "source", Map.of("type", "manual", "value", "business-type-defaults"),
                "locale", Map.of("language", "en", "country", "US"),
                "fields", fields,
                "scenarios", List.of(
                    Map.of(
                        "id", "default_business_types",
                        "kind", "positive",
                        "description", "Generate one value for every supported business type.",
                        "fields", Map.of()
                    )
                ),
                "generation", Map.of("deterministic", true, "defaultSeed", "business-type-suite"),
                "validation", Map.of("status", "valid")
            )
        );
    }

    private static JsonNode generatedImportNegativeContract() {
        return OBJECT_MAPPER.valueToTree(
            Map.of(
                "schemaVersion", "1.0",
                "id", "generated-import-negatives",
                "source", Map.of("type", "manual", "value", "generated-import-negatives"),
                "locale", Map.of("language", "en", "country", "US"),
                "fields", Map.of(
                    "phone", Map.of("dataType", "string", "businessType", "phone_number", "required", true),
                    "password", Map.of("dataType", "string", "businessType", "password", "required", true)
                ),
                "scenarios", List.of(
                    Map.of(
                        "id", "invalid_phone_format",
                        "kind", "negative",
                        "description", "Phone field contains an invalid number.",
                        "fields", Map.of("phone", Map.of("strategy", "invalid_phone_format"))
                    ),
                    Map.of(
                        "id", "weak_password",
                        "kind", "negative",
                        "description", "Password field contains an obviously weak value.",
                        "fields", Map.of("password", Map.of("strategy", "weak_password"))
                    )
                ),
                "generation", Map.of("deterministic", true, "defaultSeed", "generated-import-suite"),
                "validation", Map.of("status", "valid")
            )
        );
    }

    private static JsonNode advancedGenerationContract() {
        Map<String, Object> fields = new LinkedHashMap<>();
        fields.put(
            "email",
            Map.of(
                "dataType", "string",
                "businessType", "email",
                "required", true,
                "constraints", Map.of("format", "email", "unique", true)
            )
        );
        fields.put(
            "password",
            Map.of(
                "dataType", "string",
                "businessType", "password",
                "required", true,
                "constraints", Map.of("minLength", 12, "maxLength", 72)
            )
        );
        fields.put(
            "confirmPassword",
            Map.of(
                "dataType", "string",
                "businessType", "password",
                "required", true,
                "constraints", Map.of("minLength", 12, "maxLength", 72),
                "dependencies", Map.of("matchesField", "password")
            )
        );
        fields.put(
            "startDate",
            Map.of(
                "dataType", "date",
                "businessType", "date",
                "required", true,
                "dependencies", Map.of("rangeStartFor", "endDate")
            )
        );
        fields.put(
            "endDate",
            Map.of(
                "dataType", "date",
                "businessType", "date",
                "required", true,
                "dependencies", Map.of("rangeEndFor", "startDate")
            )
        );
        fields.put(
            "minGuests",
            Map.of(
                "dataType", "integer",
                "businessType", "integer",
                "required", true,
                "constraints", Map.of("minimum", 1, "maximum", 5),
                "dependencies", Map.of("minFor", "maxGuests")
            )
        );
        fields.put(
            "maxGuests",
            Map.of(
                "dataType", "integer",
                "businessType", "integer",
                "required", true,
                "constraints", Map.of("minimum", 1, "maximum", 10),
                "dependencies", Map.of("maxFor", "minGuests")
            )
        );
        fields.put(
            "notes",
            Map.of(
                "dataType", "string",
                "businessType", "free_text",
                "required", false,
                "constraints", Map.of("minLength", 3, "maxLength", 10)
            )
        );
        fields.put(
            "marketingOptIn",
            Map.of("dataType", "boolean", "businessType", "boolean", "required", false)
        );

        return OBJECT_MAPPER.valueToTree(
            Map.of(
                "schemaVersion", "1.0",
                "id", "advanced-generation",
                "source", Map.of("type", "manual", "value", "advanced-generation"),
                "locale", Map.of("language", "en", "country", "US"),
                "fields", fields,
                "scenarios", List.of(
                    Map.of(
                        "id", "valid_advanced",
                        "kind", "positive",
                        "description", "Valid advanced fields.",
                        "fields", Map.of()
                    ),
                    Map.of(
                        "id", "explicit_valid_relationships",
                        "kind", "positive",
                        "description", "Explicit relational strategies.",
                        "fields", Map.of(
                            "confirmPassword", Map.of("strategy", "match_field"),
                            "endDate", Map.of("strategy", "date_after_related_field"),
                            "maxGuests", Map.of("strategy", "numeric_max_at_or_above_min")
                        )
                    ),
                    Map.of(
                        "id", "range_end_after_start_relationship",
                        "kind", "positive",
                        "description", "Range end strategy keeps end date after start date.",
                        "fields", Map.of("endDate", Map.of("strategy", "range_end_after_start"))
                    ),
                    Map.of(
                        "id", "normal_strategy_confirmation_matches",
                        "kind", "positive",
                        "description", "Generated dependent fields honor dependencies after normal strategy generation.",
                        "fields", Map.of("confirmPassword", Map.of("strategy", "weak_password"))
                    ),
                    Map.of(
                        "id", "xss_payloads",
                        "kind", "security",
                        "description", "XSS probe.",
                        "fields", Map.of("notes", Map.of("strategy", "xss_payload"))
                    ),
                    Map.of(
                        "id", "sql_injection_payloads",
                        "kind", "security",
                        "description", "SQL injection probe.",
                        "fields", Map.of("notes", Map.of("strategy", "sql_injection_payload"))
                    ),
                    Map.of(
                        "id", "null_required_fields",
                        "kind", "negative",
                        "description", "Null required field.",
                        "fields", Map.of("email", Map.of("strategy", "null_value"))
                    ),
                    Map.of(
                        "id", "empty_string_fields",
                        "kind", "negative",
                        "description", "Empty string field.",
                        "fields", Map.of("notes", Map.of("strategy", "empty_string"))
                    ),
                    Map.of(
                        "id", "empty_dependent_date_field",
                        "kind", "negative",
                        "description", "Empty string on a dependent date field.",
                        "fields", Map.of("endDate", Map.of("strategy", "empty_string"))
                    ),
                    Map.of(
                        "id", "whitespace_only_fields",
                        "kind", "negative",
                        "description", "Whitespace-only field.",
                        "fields", Map.of("notes", Map.of("strategy", "whitespace_only"))
                    ),
                    Map.of(
                        "id", "below_min_length_fields",
                        "kind", "negative",
                        "description", "Below minimum length.",
                        "fields", Map.of("notes", Map.of("strategy", "below_min_length"))
                    ),
                    Map.of(
                        "id", "over_max_length_fields",
                        "kind", "negative",
                        "description", "Over maximum length.",
                        "fields", Map.of("notes", Map.of("strategy", "over_max_length"))
                    ),
                    Map.of(
                        "id", "duplicate_unique_fields",
                        "kind", "negative",
                        "description", "Duplicate unique field.",
                        "fields", Map.of("email", Map.of("strategy", "duplicate_value"))
                    ),
                    Map.of(
                        "id", "boolean_false_boundaries",
                        "kind", "boundary",
                        "description", "False boolean.",
                        "fields", Map.of("marketingOptIn", Map.of("strategy", "boolean_false"))
                    ),
                    Map.of(
                        "id", "boolean_true_boundaries",
                        "kind", "boundary",
                        "description", "True boolean.",
                        "fields", Map.of("marketingOptIn", Map.of("strategy", "boolean_true"))
                    ),
                    Map.of(
                        "id", "mismatched_confirmation_fields",
                        "kind", "negative",
                        "description", "Password confirmation mismatch.",
                        "fields", Map.of("confirmPassword", Map.of("strategy", "mismatch_field"))
                    ),
                    Map.of(
                        "id", "invalid_date_ranges",
                        "kind", "negative",
                        "description", "Date range is reversed.",
                        "fields", Map.of("endDate", Map.of("strategy", "date_before_related_field"))
                    ),
                    Map.of(
                        "id", "invalid_numeric_ranges",
                        "kind", "negative",
                        "description", "Maximum is below minimum.",
                        "fields", Map.of("maxGuests", Map.of("strategy", "numeric_max_below_min"))
                    )
                ),
                "generation", Map.of("deterministic", true, "defaultSeed", "advanced-generation-suite"),
                "validation", Map.of("status", "valid")
            )
        );
    }

    private static Map<String, Object> businessTypeField(String businessType) {
        Map<String, Object> field = new LinkedHashMap<>();
        field.put("dataType", dataTypeFor(businessType));
        field.put("businessType", businessType);
        field.put("required", false);
        if ("enum".equals(businessType)) {
            field.put("constraints", Map.of("values", List.of("basic", "pro", "enterprise")));
        } else if (Set.of("integer", "quantity").contains(businessType)) {
            field.put("constraints", Map.of("minimum", 10, "maximum", 20));
        } else if (Set.of("decimal", "amount", "percentage").contains(businessType)) {
            field.put("constraints", Map.of("minimum", 1, "maximum", 9));
        } else if ("phone_number".equals(businessType)) {
            field.put("constraints", Map.of("country", "US"));
        }
        return field;
    }

    private static String dataTypeFor(String businessType) {
        return switch (businessType) {
            case "integer", "quantity" -> "integer";
            case "decimal", "amount", "percentage" -> "decimal";
            case "boolean" -> "boolean";
            case "enum" -> "enum";
            case "date", "date_of_birth" -> "date";
            case "time" -> "time";
            case "datetime" -> "datetime";
            default -> "string";
        };
    }

    private static void assertBusinessTypeRecord(Map<String, Object> record) {
        assertTrue(record.get("email").toString().endsWith("@example.test"));
        assertTrue(record.get("phone_number").toString().matches("\\+155501\\d{4}"));
        assertTrue(record.get("country_code").toString().matches("[A-Z]{2}"));
        assertTrue(record.get("address_line").toString().matches("\\d{3} [A-Za-z ]+"));
        assertTrue(record.get("postal_code").toString().matches("\\d{5}"));
        assertTrue(record.get("currency").toString().matches("[A-Z]{3}"));
        assertTrue(record.get("url").toString().matches("https://app-\\d{3}\\.example\\.test/resource-1"));
        assertTrue(record.get("domain").toString().matches("service-\\d{3}\\.example\\.test"));
        UUID.fromString(record.get("uuid").toString());
        assertTrue(record.get("national_id").toString().matches("NID-\\d{9}"));
        assertTrue(record.get("passport_number").toString().matches("[PTX]\\d{8}"));
        assertTrue(record.get("tax_id").toString().matches("TAX-\\d{8}"));
        assertTrue(record.get("account_number").toString().matches("000\\d{9}"));
        assertTrue(ibanIsValid(record.get("iban").toString()));
        assertTrue(record.get("credit_card_number").toString().startsWith("411111"));
        assertTrue(luhnIsValid(record.get("credit_card_number").toString()));
        assertTrue(record.get("cvv").toString().matches("\\d{3}"));
        assertTrue(record.get("expiry_date").toString().matches("\\d{2}/3\\d"));
        assertTrue(record.get("otp").toString().matches("\\d{6}"));
        OffsetDateTime.parse(record.get("datetime").toString());
        LocalTime.parse(record.get("time").toString());
    }

    private static boolean ibanIsValid(String value) {
        return value.matches("GB\\d{2}TEST\\d{14}") && ibanMod97(value.substring(4) + value.substring(0, 4)) == 1;
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
                return -1;
            }
            for (int digitIndex = 0; digitIndex < digits.length(); digitIndex += 1) {
                remainder = (remainder * 10 + Character.digit(digits.charAt(digitIndex), 10)) % 97;
            }
        }
        return remainder;
    }

    private static boolean luhnIsValid(String value) {
        int total = 0;
        for (int index = value.length() - 1, position = 0; index >= 0; index -= 1, position += 1) {
            int digit = Character.digit(value.charAt(index), 10);
            if (position % 2 == 1) {
                digit *= 2;
                if (digit > 9) {
                    digit -= 9;
                }
            }
            total += digit;
        }
        return total % 10 == 0;
    }
}
