// testbenches/peripherals/uart_tx_known_good.sv
// Hand-written, known-correct 8N1 UART transmitter, used only to validate
// the eval harness itself.
module uart_tx (
    input  logic clk, rst_n, tx_start,
    input  logic [7:0] data,
    output logic tx, busy
);
    typedef enum logic [1:0] {IDLE, START, DATA, STOP} state_t;
    state_t state;
    logic [2:0] bit_idx;
    logic [7:0] shift_reg;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE; tx <= 1'b1; busy <= 1'b0; bit_idx <= 0;
        end else begin
            case (state)
                IDLE: begin
                    tx <= 1'b1;
                    if (tx_start) begin
                        state <= START; busy <= 1'b1; shift_reg <= data;
                    end
                end
                START: begin tx <= 1'b0; state <= DATA; bit_idx <= 0; end
                DATA: begin
                    tx <= shift_reg[bit_idx];
                    if (bit_idx == 3'd7) state <= STOP;
                    else bit_idx <= bit_idx + 1;
                end
                STOP: begin tx <= 1'b1; busy <= 1'b0; state <= IDLE; end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
