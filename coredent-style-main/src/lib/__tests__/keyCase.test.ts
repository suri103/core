import { describe, it, expect } from "vitest";
import {
  snakeToCamelKey,
  camelToSnakeKey,
  snakeToCamel,
  camelToSnake,
} from "../keyCase";

describe("keyCase transforms", () => {
  describe("snakeToCamelKey", () => {
    it("converts snake_case to camelCase", () => {
      expect(snakeToCamelKey("first_name")).toBe("firstName");
      expect(snakeToCamelKey("date_of_birth")).toBe("dateOfBirth");
      expect(snakeToCamelKey("has_medical_alerts")).toBe("hasMedicalAlerts");
    });

    it("leaves dialect-free keys untouched", () => {
      expect(snakeToCamelKey("id")).toBe("id");
      expect(snakeToCamelKey("email")).toBe("email");
      expect(snakeToCamelKey("firstName")).toBe("firstName");
    });
  });

  describe("camelToSnakeKey", () => {
    it("converts camelCase to snake_case", () => {
      expect(camelToSnakeKey("firstName")).toBe("first_name");
      expect(camelToSnakeKey("dateOfBirth")).toBe("date_of_birth");
      expect(camelToSnakeKey("hasMedicalAlerts")).toBe("has_medical_alerts");
    });

    it("leaves dialect-free and already-snake keys untouched", () => {
      expect(camelToSnakeKey("id")).toBe("id");
      expect(camelToSnakeKey("first_name")).toBe("first_name");
    });
  });

  describe("snakeToCamel", () => {
    it("recursively converts nested objects and arrays", () => {
      const input = {
        patient_id: "p-1",
        emergency_contact: { phone: "555" },
        medical_alerts: ["a", "b"],
        nested_list: [{ inner_value: 1 }],
      };
      expect(snakeToCamel(input)).toEqual({
        patientId: "p-1",
        emergencyContact: { phone: "555" },
        medicalAlerts: ["a", "b"],
        nestedList: [{ innerValue: 1 }],
      });
    });

    it("returns primitives and null unchanged", () => {
      expect(snakeToCamel("plain")).toBe("plain");
      expect(snakeToCamel(42)).toBe(42);
      expect(snakeToCamel(null)).toBeNull();
      expect(snakeToCamel(undefined)).toBeUndefined();
    });
  });

  describe("camelToSnake", () => {
    it("recursively converts nested objects and arrays", () => {
      const input = {
        patientId: "p-1",
        emergencyContact: { phone: "555" },
        nestedList: [{ innerValue: 1 }],
      };
      expect(camelToSnake(input)).toEqual({
        patient_id: "p-1",
        emergency_contact: { phone: "555" },
        nested_list: [{ inner_value: 1 }],
      });
    });

    it("is idempotent on already-snake trees", () => {
      const snake = { first_name: "Jane", address_zip: "62701" };
      expect(camelToSnake(snake)).toEqual(snake);
    });
  });
});