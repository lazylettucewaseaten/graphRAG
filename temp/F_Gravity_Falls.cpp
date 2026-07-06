#include <iostream>
#include <string>

// --- Class 1: A utility class with a recursive function ---
class MathEngine {
public:
    // A standard method with multiple parameters
    int add(int a, int b) {
        return a + b;
    }

    // A standard method with double types
    double multiply(double x, double y) {
        return x * y;
    }

    // A recursive method (Tree-sitter will see a call_expression calling itself)
    int computeFactorial(int n) {
        if (n <= 1) {
            return 1;
        }
        return n * computeFactorial(n - 1);
    }
};

// --- Class 2: A processor class that invokes the MathEngine ---
class Calculator {
private:
    std::string modelName;
    MathEngine engine; // Class invoking another class (Composition)

public:
    // Constructor
    Calculator(std::string name) {
        modelName = name;
    }

    // A standard void function
    void displayGreeting() {
        std::cout << "Starting " << modelName << "...\n";
    }

    // A function that calls methods from the other class
    void runDemo() {
        // Tree-sitter will parse these as field_expression -> call_expression
        int sumResult = engine.add(10, 25);
        double multResult = engine.multiply(3.14, 2.0);
        int factResult = engine.computeFactorial(5);

        std::cout << "Sum: " << sumResult << "\n";
        std::cout << "Product: " << multResult << "\n";
        std::cout << "Factorial (5!): " << factResult << "\n";
    }
};

// --- Main function to tie it all together ---
int main() {
    // Instantiate the class
    Calculator myCalc("AST-Pro-9000");
    
    // Execute methods
    myCalc.displayGreeting();
    myCalc.runDemo();

    return 0;
}